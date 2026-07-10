"""
Post-install verification for the air-gapped deployment.

Run inside the project's virtual environment:

    .venv\\Scripts\\python offline\\verify_install.py

Checks, in order:
  1. Python version matches the wheel target (3.12).
  2. Every dependency imports.
  3. The embedding model loads FROM LOCAL DISK with Hugging Face offline
     mode forced, and produces an embedding of the expected dimension.
  4. ChromaDB persistent store round-trips a vector.
  5. The restricted calculation tool executes and enforces its guardrails.
  6. Configuration sanity (auth mode vs transport, kerberos/oauth settings).
  7. PI Web API connectivity (only if PI_WEBAPI_URL is configured).

Exit code 0 = ready to run. Non-zero = fix the reported item first.
"""

from __future__ import annotations

import os
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

PASS, FAIL, WARN = "  [OK]  ", "  [FAIL]", "  [WARN]"
failures: list[str] = []


def check(label: str, fn) -> None:
    try:
        detail = fn() or ""
        print(f"{PASS} {label}  {detail}")
    except Exception as exc:
        failures.append(label)
        print(f"{FAIL} {label}: {exc}")
        if os.getenv("VERIFY_VERBOSE"):
            traceback.print_exc()


def main() -> int:
    print("=" * 64)
    print("PI Advisor ADN — installation verification")
    print("=" * 64)

    # 1 — interpreter
    def _py():
        v = sys.version_info
        if (v.major, v.minor) != (3, 12):
            raise RuntimeError(f"expected Python 3.12, found {v.major}.{v.minor}")
        return f"({sys.version.split()[0]})"
    check("Python version", _py)

    # 2 — imports
    for mod in ("fastmcp", "aiohttp", "pandas", "numpy", "chromadb",
                "sentence_transformers", "networkx", "rank_bm25", "dotenv",
                "jwt", "uvicorn", "spnego"):
        check(f"import {mod}", lambda m=mod: __import__(m) and "")

    # config import (after deps)
    def _cfg():
        from config import config  # noqa: F401
        return ""
    check("project config loads", _cfg)

    # 3 — embedding model, strictly offline
    def _model():
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        from config import config
        path = config.embedding.model
        if not os.path.isdir(path):
            raise RuntimeError(
                f"EMBEDDING_MODEL is not a local directory: {path!r} — "
                f"copy the bundled models\\bge-base-en-v1.5 folder and set "
                f"EMBEDDING_MODEL accordingly"
            )
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(path, device=config.embedding.device)
        vec = model.encode(["gas separator pressure"], normalize_embeddings=True)
        if vec.shape != (1, 768):
            raise RuntimeError(f"unexpected embedding shape {vec.shape}")
        return f"(dim=768, offline mode, {os.path.basename(path)})"
    check("embedding model loads offline", _model)

    # 4 — chroma round trip
    def _chroma():
        import chromadb
        d = tempfile.mkdtemp(prefix="verify_chroma_")
        client = chromadb.PersistentClient(path=d)
        col = client.get_or_create_collection("verify", metadata={"hnsw:space": "cosine"})
        col.upsert(ids=["1"], embeddings=[[0.1] * 8], documents=["t"])
        res = col.query(query_embeddings=[[0.1] * 8], n_results=1)
        if res["ids"] != [["1"]]:
            raise RuntimeError("query did not return the inserted document")
        return ""
    check("chromadb persistent round-trip", _chroma)

    # 5 — calculation tool
    def _calc():
        from calc_tool import run_calculation_sync
        ok = run_calculation_sync("result = float(pd.Series([1, 2, 3]).mean())")
        if ok.get("result") != 2.0:
            raise RuntimeError(f"unexpected result: {ok}")
        blocked = run_calculation_sync("import os")
        if "error" not in blocked:
            raise RuntimeError("import was NOT blocked")
        return ""
    check("restricted calc tool (works + blocks imports)", _calc)

    # 6 — configuration sanity
    def _sanity():
        from config import config
        notes = []
        if config.server.transport == "http":
            if config.auth.mode == "none":
                raise RuntimeError("MCP_TRANSPORT=http with AUTH_MODE=none — set api_key or entra_jwt")
            from auth import init_auth
            init_auth()  # raises on incomplete auth settings
            if not (config.server.ssl_certfile or ""):
                notes.append("no TLS cert set — ensure a reverse proxy terminates HTTPS")
        if config.pi.auth_method == "oauth" and not config.pi.oauth_token_url:
            raise RuntimeError("PI_AUTH_METHOD=oauth but PI_OAUTH_TOKEN_URL is empty")
        if config.pi.auth_method == "basic":
            notes.append("PI_AUTH_METHOD=basic — use kerberos or oauth outside the lab")
        if not config.pi.verify_ssl:
            notes.append("PI_VERIFY_SSL=false — set PI_CA_BUNDLE to the internal CA instead")
        return ("; ".join(notes)) if notes else ""
    check("configuration sanity", _sanity)

    # 7 — PI connectivity (optional)
    from config import config
    if config.pi.url and "<" not in config.pi.url:
        def _pi():
            import asyncio
            from pi_client import get_client, close_client
            async def probe():
                try:
                    return await get_client().test_connection()
                finally:
                    await close_client()
            res = asyncio.run(probe())
            return f"(version {res.get('version')}, {res.get('response_ms')} ms, auth={res.get('auth_method')})"
        check("PI Web API connectivity", _pi)
    else:
        print(f"{WARN}  PI Web API connectivity skipped — PI_WEBAPI_URL not configured yet")

    print("=" * 64)
    if failures:
        print(f"RESULT: {len(failures)} check(s) FAILED: {', '.join(failures)}")
        return 1
    print("RESULT: all checks passed — the installation is ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

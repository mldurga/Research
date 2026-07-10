"""
Download the embedding model for offline use.

Run on the INTERNET-CONNECTED prep machine only:

    pip install "huggingface_hub>=0.23"
    python download_model.py [target_dir]

Downloads BAAI/bge-base-en-v1.5 (~430 MB) into <target_dir>/bge-base-en-v1.5
as plain files (no symlinks, no HF cache indirection) so the directory can be
copied as-is to the air-gapped server and referenced via:

    EMBEDDING_MODEL=models\\bge-base-en-v1.5
"""

from __future__ import annotations

import sys
from pathlib import Path

MODEL_ID = "BAAI/bge-base-en-v1.5"

# Everything sentence-transformers needs at load time; excludes the large
# duplicate checkpoint formats we don't use (onnx/openvino/tf).
ALLOW_PATTERNS = [
    "*.json",
    "*.txt",
    "model.safetensors",
    "1_Pooling/*",
]


def main() -> None:
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        sys.exit("huggingface_hub is not installed. Run: pip install 'huggingface_hub>=0.23'")

    target_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "models"
    target = target_root / "bge-base-en-v1.5"
    target.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {MODEL_ID} -> {target}")
    snapshot_download(
        repo_id=MODEL_ID,
        local_dir=str(target),
        allow_patterns=ALLOW_PATTERNS,
    )

    required = ["config.json", "model.safetensors", "tokenizer.json", "config_sentence_transformers.json"]
    missing = [f for f in required if not (target / f).exists()]
    if missing:
        sys.exit(f"Download incomplete — missing: {missing}")

    size_mb = sum(p.stat().st_size for p in target.rglob("*") if p.is_file()) / 1e6
    print(f"OK — model complete ({size_mb:.0f} MB) at {target}")


if __name__ == "__main__":
    main()

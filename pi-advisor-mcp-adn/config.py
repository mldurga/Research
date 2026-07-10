"""
Env-driven configuration — ADN (Air-gapped Deployment / WiNdows) edition.

Differences from the base pi-advisor-mcp config:
  * ServerConfig      — MCP transport (stdio | http), bind host/port, TLS.
  * InboundAuthConfig — authentication of INCOMING MCP calls
                        (none | api_key | entra_jwt) plus a caller allowlist.
  * PISystemConfig    — extended with Kerberos (SSPI) and OAuth
                        client-credentials settings for the two PI Web API
                        gateways, plus an internal CA bundle option.
  * EmbeddingConfig   — supports a LOCAL model directory; when the model is a
                        local path, Hugging Face offline mode is forced so the
                        process never attempts to reach the internet.
  * CalcToolConfig    — optional restricted Python calculation tool.

Everything is read from a .env file anchored to this package directory, so the
server behaves identically no matter which working directory the MCP client
(or the Windows service wrapper) launches it from.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

from dotenv import load_dotenv

# Anchor .env loading and all relative data paths to THIS file's directory.
_HERE = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(_HERE, ".env"))


def _anchored(path: str) -> str:
    """Resolve a possibly-relative path against the package directory."""
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(_HERE, path))


def _env_bool(key: str, default: bool) -> bool:
    return os.getenv(key, str(default)).strip().lower() in ("1", "true", "yes")


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _env_list(key: str) -> List[str]:
    """Parse a comma-separated env var into a list of trimmed strings."""
    raw = os.getenv(key, "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


# --------------------------------------------------------------------------- #
# MCP server (transport + inbound security)
# --------------------------------------------------------------------------- #

@dataclass
class ServerConfig:
    # stdio  — launched as a subprocess by a local MCP client (dev/testing).
    # http   — MCP streamable HTTP endpoint (required for Copilot Studio).
    transport: str = field(default_factory=lambda: os.getenv("MCP_TRANSPORT", "stdio").lower())
    host: str = field(default_factory=lambda: os.getenv("MCP_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _env_int("MCP_PORT", 8443))
    # TLS served directly by uvicorn.  Leave empty if a reverse proxy
    # (IIS/ARR, nginx) terminates TLS in front of this process instead.
    ssl_certfile: str = field(default_factory=lambda: os.getenv("MCP_SSL_CERTFILE", ""))
    ssl_keyfile: str = field(default_factory=lambda: os.getenv("MCP_SSL_KEYFILE", ""))


@dataclass
class InboundAuthConfig:
    # none      — no auth (local stdio testing ONLY, never for the http transport)
    # api_key   — static key(s) in the X-API-Key header
    # entra_jwt — validate Microsoft Entra ID bearer tokens (JWT, RS256)
    mode: str = field(default_factory=lambda: os.getenv("AUTH_MODE", "none").lower())

    # ---- api_key mode ----
    api_keys: List[str] = field(default_factory=lambda: _env_list("AUTH_API_KEYS"))

    # ---- entra_jwt mode ----
    tenant_id: str = field(default_factory=lambda: os.getenv("AUTH_ENTRA_TENANT_ID", ""))
    # Expected 'aud' claim, e.g. api://<server-app-client-id> or the app's client id.
    audience: str = field(default_factory=lambda: os.getenv("AUTH_ENTRA_AUDIENCE", ""))
    # Expected 'iss' claim. Default is built from tenant_id (v2 endpoint) if empty.
    issuer: str = field(default_factory=lambda: os.getenv("AUTH_ENTRA_ISSUER", ""))
    # Where to get token-signing public keys:
    #   AUTH_JWKS_URL  — fetched over the network (works if the identity
    #                    endpoint is reachable INSIDE the private environment)
    #   AUTH_JWKS_FILE — a local jwks.json exported ahead of time
    #                    (fully offline; refresh it when keys rotate)
    jwks_url: str = field(default_factory=lambda: os.getenv("AUTH_JWKS_URL", ""))
    jwks_file: str = field(default_factory=lambda: (
        _anchored(os.getenv("AUTH_JWKS_FILE")) if os.getenv("AUTH_JWKS_FILE") else ""
    ))

    # ---- caller allowlist (applies to entra_jwt mode) ----
    # Empty lists = any valid token from the tenant is accepted (logged with a warning).
    # Users: match against oid / upn / preferred_username / email claims.
    allowed_users: List[str] = field(default_factory=lambda: _env_list("AUTH_ALLOWED_USERS"))
    # Groups: match against the 'groups' claim (group object IDs).
    allowed_groups: List[str] = field(default_factory=lambda: _env_list("AUTH_ALLOWED_GROUPS"))
    # Applications: match against appid / azp claims (client-credential callers,
    # e.g. the Copilot Studio connector's app registration).
    allowed_apps: List[str] = field(default_factory=lambda: _env_list("AUTH_ALLOWED_APPS"))


# --------------------------------------------------------------------------- #
# PI Web API (outbound)
# --------------------------------------------------------------------------- #

@dataclass
class PISystemConfig:
    url: str = field(default_factory=lambda: os.getenv("PI_WEBAPI_URL", ""))
    af_server: str = field(default_factory=lambda: os.getenv("AF_SERVER_NAME", ""))
    af_database: str = field(default_factory=lambda: os.getenv("AF_DATABASE_NAME", ""))
    data_server: str = field(default_factory=lambda: os.getenv("DATA_SERVER_NAME", ""))

    # basic | kerberos | oauth | bearer
    auth_method: str = field(default_factory=lambda: os.getenv("PI_AUTH_METHOD", "kerberos").lower())

    # ---- basic ----
    username: Optional[str] = field(default_factory=lambda: os.getenv("PI_USERNAME"))
    password: Optional[str] = field(default_factory=lambda: os.getenv("PI_PASSWORD"))

    # ---- kerberos (Windows SSPI via pyspnego) ----
    # By default the token is acquired for the identity of the PROCESS
    # (the service account the Windows service/task runs as) against
    # SPN HTTP/<host-from-PI_WEBAPI_URL>.  Override only if the gateway
    # registered a different SPN.
    kerberos_service: str = field(default_factory=lambda: os.getenv("PI_KERBEROS_SERVICE", "HTTP"))
    kerberos_hostname: str = field(default_factory=lambda: os.getenv("PI_KERBEROS_HOSTNAME", ""))
    # Optional explicit domain credentials (DOMAIN\\user) instead of the
    # process identity. Usually leave empty and run the service as the
    # designated service account.
    kerberos_username: Optional[str] = field(default_factory=lambda: os.getenv("PI_KERBEROS_USERNAME"))
    kerberos_password: Optional[str] = field(default_factory=lambda: os.getenv("PI_KERBEROS_PASSWORD"))

    # ---- oauth (client credentials against the OAuth gateway) ----
    oauth_token_url: str = field(default_factory=lambda: os.getenv("PI_OAUTH_TOKEN_URL", ""))
    oauth_client_id: str = field(default_factory=lambda: os.getenv("PI_OAUTH_CLIENT_ID", ""))
    oauth_client_secret: str = field(default_factory=lambda: os.getenv("PI_OAUTH_CLIENT_SECRET", ""))
    oauth_scope: str = field(default_factory=lambda: os.getenv("PI_OAUTH_SCOPE", ""))
    # Some gateways use 'resource' (v1-style) instead of 'scope'.
    oauth_resource: str = field(default_factory=lambda: os.getenv("PI_OAUTH_RESOURCE", ""))

    # ---- bearer (static token supplied out-of-band) ----
    bearer_token: str = field(default_factory=lambda: os.getenv("PI_BEARER_TOKEN", ""))

    # ---- TLS ----
    verify_ssl: bool = field(default_factory=lambda: _env_bool("PI_VERIFY_SSL", True))
    # Path to the internal enterprise CA bundle (PEM). Preferred over
    # PI_VERIFY_SSL=false in any shared environment.
    ca_bundle: str = field(default_factory=lambda: (
        _anchored(os.getenv("PI_CA_BUNDLE")) if os.getenv("PI_CA_BUNDLE") else ""
    ))

    timeout: int = field(default_factory=lambda: _env_int("PI_TIMEOUT", 30))
    connection_limit: int = 100
    per_host_limit: int = 30


# --------------------------------------------------------------------------- #
# Embedding model (offline-first)
# --------------------------------------------------------------------------- #

@dataclass
class EmbeddingConfig:
    # In the air-gapped deployment this MUST be a local directory containing
    # the pre-downloaded model (see offline/download_model.py), e.g.
    #   EMBEDDING_MODEL=models/bge-base-en-v1.5      (relative to this package)
    # A Hugging Face model ID still works on internet-connected dev machines.
    model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "models/bge-base-en-v1.5"))
    device: str = field(default_factory=lambda: os.getenv("EMBEDDING_DEVICE", "cpu"))
    # BGE models benefit from instruction prefix at query time
    query_instruction: str = "Represent this sentence for searching relevant passages: "

    def __post_init__(self) -> None:
        # If the model is a local path, anchor it and force full offline mode
        # so transformers/huggingface_hub never attempt a network call.
        candidate = _anchored(self.model)
        if os.path.isdir(candidate):
            self.model = candidate
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


# --------------------------------------------------------------------------- #
# Stores / indexes (unchanged from base edition)
# --------------------------------------------------------------------------- #

@dataclass
class ChromaDBConfig:
    client_type: str = field(default_factory=lambda: os.getenv("CHROMA_CLIENT_TYPE", "persistent"))
    data_dir: str = field(default_factory=lambda: _anchored(os.getenv("CHROMA_DATA_DIR", "chroma_data")))
    host: Optional[str] = field(default_factory=lambda: os.getenv("CHROMA_HOST"))
    port: Optional[int] = field(default_factory=lambda: (
        int(os.getenv("CHROMA_PORT")) if os.getenv("CHROMA_PORT") else None
    ))
    api_key: Optional[str] = field(default_factory=lambda: os.getenv("CHROMA_API_KEY"))
    collection_name: str = field(default_factory=lambda: os.getenv("CHROMA_COLLECTION", "af_elements"))


@dataclass
class KnowledgeGraphConfig:
    enabled: bool = field(default_factory=lambda: _env_bool("KG_ENABLED", True))
    persist_path: str = field(default_factory=lambda: _anchored(os.getenv("KG_PERSIST_PATH", "graph_data")))
    max_depth: int = field(default_factory=lambda: _env_int("KG_MAX_DEPTH", 10))


@dataclass
class BM25Config:
    enabled: bool = field(default_factory=lambda: _env_bool("BM25_ENABLED", True))
    persist_path: str = field(default_factory=lambda: _anchored(os.getenv("BM25_PERSIST_PATH", "bm25_data")))
    k1: float = 1.5
    b: float = 0.75
    top_k: int = 20


@dataclass
class IndexingConfig:
    enabled: bool = field(default_factory=lambda: _env_bool("INDEXING_ENABLED", True))
    refresh_hours: int = field(default_factory=lambda: _env_int("INDEXING_REFRESH_HOURS", 24))
    batch_size: int = field(default_factory=lambda: _env_int("INDEXING_BATCH_SIZE", 50))
    max_elements: int = field(default_factory=lambda: _env_int("INDEXING_MAX_ELEMENTS", 10000))
    concurrency: int = field(default_factory=lambda: _env_int("INDEXING_CONCURRENCY", 20))
    max_attrs_per_element: int = 100
    # Root-subtree scoping: comma-separated AF element paths to index from.
    root_paths: List[str] = field(default_factory=lambda: _env_list("INDEX_ROOT_PATHS"))


@dataclass
class CacheConfig:
    enabled: bool = field(default_factory=lambda: _env_bool("CACHE_ENABLED", True))
    max_size: int = field(default_factory=lambda: _env_int("CACHE_MAX_SIZE", 500))
    current_value_ttl: int = field(default_factory=lambda: _env_int("CACHE_CURRENT_VALUE_TTL", 30))
    summary_ttl: int = field(default_factory=lambda: _env_int("CACHE_SUMMARY_TTL", 300))
    health_ttl: int = field(default_factory=lambda: _env_int("CACHE_HEALTH_TTL", 60))
    structural_ttl: int = field(default_factory=lambda: _env_int("CACHE_STRUCTURAL_TTL", 600))
    resolution_ttl: int = field(default_factory=lambda: _env_int("CACHE_RESOLUTION_TTL", 900))
    forecast_ttl: int = field(default_factory=lambda: _env_int("CACHE_FORECAST_TTL", 3600))


# --------------------------------------------------------------------------- #
# Optional restricted calculation tool
# --------------------------------------------------------------------------- #

@dataclass
class CalcToolConfig:
    enabled: bool = field(default_factory=lambda: _env_bool("CALC_TOOL_ENABLED", True))
    timeout_seconds: int = field(default_factory=lambda: _env_int("CALC_TOOL_TIMEOUT", 10))
    max_output_chars: int = field(default_factory=lambda: _env_int("CALC_TOOL_MAX_OUTPUT", 50_000))


# --------------------------------------------------------------------------- #
# Root config
# --------------------------------------------------------------------------- #

@dataclass
class AppConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    auth: InboundAuthConfig = field(default_factory=InboundAuthConfig)
    pi: PISystemConfig = field(default_factory=PISystemConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    chromadb: ChromaDBConfig = field(default_factory=ChromaDBConfig)
    graph: KnowledgeGraphConfig = field(default_factory=KnowledgeGraphConfig)
    bm25: BM25Config = field(default_factory=BM25Config)
    indexing: IndexingConfig = field(default_factory=IndexingConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    calc: CalcToolConfig = field(default_factory=CalcToolConfig)
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))


# Single global config instance loaded once at import time.
config = AppConfig()

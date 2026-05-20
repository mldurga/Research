from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

from dotenv import load_dotenv

# Anchor .env loading and all relative data paths to THIS file's directory,
# so the server behaves identically regardless of the process working
# directory. This matters when an MCP client (e.g. Hermes) launches the
# server as a subprocess from its own directory.
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


@dataclass
class PISystemConfig:
    url: str = field(default_factory=lambda: os.getenv("PI_WEBAPI_URL", ""))
    af_server: str = field(default_factory=lambda: os.getenv("AF_SERVER_NAME", ""))
    af_database: str = field(default_factory=lambda: os.getenv("AF_DATABASE_NAME", ""))
    data_server: str = field(default_factory=lambda: os.getenv("DATA_SERVER_NAME", ""))
    username: Optional[str] = field(default_factory=lambda: os.getenv("PI_USERNAME"))
    password: Optional[str] = field(default_factory=lambda: os.getenv("PI_PASSWORD"))
    auth_method: str = field(default_factory=lambda: os.getenv("PI_AUTH_METHOD", "basic"))
    verify_ssl: bool = field(default_factory=lambda: _env_bool("PI_VERIFY_SSL", True))
    timeout: int = field(default_factory=lambda: _env_int("PI_TIMEOUT", 30))
    connection_limit: int = 100
    per_host_limit: int = 30


@dataclass
class EmbeddingConfig:
    model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5"))
    device: str = field(default_factory=lambda: os.getenv("EMBEDDING_DEVICE", "cpu"))
    # BGE models benefit from instruction prefix at query time
    query_instruction: str = "Represent this sentence for searching relevant passages: "


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
    # Empty list = index the entire AF database (default).
    # Each path is resolved to a WebId and indexed with its full descendant tree.
    # Example: \\AF\APAPI\Train 1,\\AF\APAPI\Train 2
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


@dataclass
class AppConfig:
    pi: PISystemConfig = field(default_factory=PISystemConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    chromadb: ChromaDBConfig = field(default_factory=ChromaDBConfig)
    graph: KnowledgeGraphConfig = field(default_factory=KnowledgeGraphConfig)
    bm25: BM25Config = field(default_factory=BM25Config)
    indexing: IndexingConfig = field(default_factory=IndexingConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))


# Single global config instance loaded once at import time.
config = AppConfig()

"""
ChromaDB vector store manager for AF element semantic search.

Uses BAAI/bge-base-en-v1.5 (768-dim, ~430 MB) via sentence-transformers.
BGE models produce better embeddings when the query is prefixed with an
instruction string at retrieval time; documents are embedded without prefix.

Collections store one document per AF element.  Rich metadata enables
post-retrieval filtering by template, measurement type, and hierarchy level
without re-ranking.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from config import config
from synonyms import expand_query, get_measurement_type

logger = logging.getLogger(__name__)

# We embed documents without the instruction prefix; queries get the prefix.
_QUERY_PREFIX = config.embedding.query_instruction


# --------------------------------------------------------------------------- #
# Document preparation
# --------------------------------------------------------------------------- #

def _prepare_document(
    element: Dict[str, Any],
    attributes: List[Dict[str, Any]],
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Build (document_text, element_id, metadata) for a single AF element.

    document_text is a rich prose description designed for semantic embedding.
    metadata contains filterable scalar fields stored alongside the vector.
    """
    webid: str = element.get("WebId", element.get("webid", ""))
    name: str = element.get("Name", element.get("name", ""))
    desc: str = element.get("Description", element.get("description", "")) or ""
    path: str = element.get("Path", element.get("path", "")) or ""
    template: str = element.get("TemplateName", element.get("template", "")) or ""
    has_children: bool = bool(element.get("HasChildren", element.get("has_children", False)))

    # --- Path decomposition ------------------------------------------------
    path_parts = [p for p in path.split("\\") if p]
    depth = len(path_parts)
    parent_path = "\\".join(path_parts[:-1]) if len(path_parts) > 1 else ""

    # --- Attribute analysis ------------------------------------------------
    attr_names: List[str] = []
    measurement_types: List[str] = []
    units: List[str] = []
    attr_flags: Dict[str, bool] = {}

    for attr in attributes[:100]:
        attr_name = attr.get("Name", "")
        if attr_name:
            attr_names.append(attr_name)
        unit = attr.get("DefaultUnitsName", "")
        if unit:
            units.append(unit)
        mt = get_measurement_type(attr_name)
        if mt != "other":
            measurement_types.append(mt)
            attr_flags[f"has_{mt.replace(' ', '_')}"] = True

    # --- Document text ----------------------------------------------------
    parts: List[str] = [
        f"Element: {name}",
    ]
    if desc:
        parts.append(f"Description: {desc}")
    if template:
        parts.append(f"Equipment type: {template}")
    if path_parts:
        parts.append(f"Location in plant: {' > '.join(path_parts)}")
    if parent_path:
        parts.append(f"Parent section: {parent_path.rsplit(chr(92), 1)[-1]}")
    if attr_names:
        parts.append(f"Monitored parameters: {', '.join(attr_names[:30])}")
    if measurement_types:
        parts.append(f"Measurement categories: {', '.join(sorted(set(measurement_types)))}")
    if units:
        parts.append(f"Engineering units: {', '.join(sorted(set(units)))}")
    if has_children:
        parts.append("Contains sub-elements.")
    else:
        parts.append("Leaf node (instrument or final asset).")

    document = "\n".join(parts)

    # --- Metadata ---------------------------------------------------------
    # ChromaDB metadata values must be scalar (str, int, float, bool).
    metadata: Dict[str, Any] = {
        "webid": webid,
        "name": name,
        "path": path,
        "parent_path": parent_path,
        "template": template,
        "depth": depth,
        "has_children": has_children,
        "is_leaf": not has_children,
        "attribute_count": len(attributes),
        "measurement_types": json.dumps(list(set(measurement_types))[:15]),
        "attribute_names": json.dumps(attr_names[:30]),
        "units": json.dumps(list(set(units))[:10]),
    }
    # Boolean flags for cheap filtering
    for flag, val in attr_flags.items():
        metadata[flag] = val

    element_id = f"af_{webid}"
    return document, element_id, metadata


# --------------------------------------------------------------------------- #
# Manager
# --------------------------------------------------------------------------- #

class VectorDBManager:
    """
    Manages the ChromaDB collection for AF element semantic search.

    Singleton-friendly: call ``get_vector_db()`` rather than constructing directly.
    """

    def __init__(self) -> None:
        self._client: Optional[chromadb.ClientAPI] = None
        self._collection: Optional[chromadb.Collection] = None
        self._embedding_fn: Optional[SentenceTransformerEmbeddingFunction] = None
        self._indexed_at: Optional[str] = None

    # ------------------------------------------------------------------ #
    # Initialisation
    # ------------------------------------------------------------------ #

    def _get_embedding_fn(self) -> SentenceTransformerEmbeddingFunction:
        if self._embedding_fn is None:
            logger.info("Loading embedding model %s on %s …", config.embedding.model, config.embedding.device)
            self._embedding_fn = SentenceTransformerEmbeddingFunction(
                model_name=config.embedding.model,
                device=config.embedding.device,
                # normalize_embeddings improves cosine similarity stability
                normalize_embeddings=True,
            )
        return self._embedding_fn

    def _get_client(self) -> chromadb.ClientAPI:
        if self._client is not None:
            return self._client

        cfg = config.chromadb
        if cfg.client_type == "persistent":
            os.makedirs(cfg.data_dir, exist_ok=True)
            self._client = chromadb.PersistentClient(path=cfg.data_dir)
        elif cfg.client_type == "ephemeral":
            self._client = chromadb.EphemeralClient()
        elif cfg.client_type == "http":
            self._client = chromadb.HttpClient(
                host=cfg.host or "localhost",
                port=cfg.port or 8000,
                ssl=False,
            )
        else:
            raise ValueError(f"Unsupported CHROMA_CLIENT_TYPE: {cfg.client_type}")
        return self._client

    def get_or_create_collection(self) -> chromadb.Collection:
        if self._collection is not None:
            return self._collection
        client = self._get_client()
        self._collection = client.get_or_create_collection(
            name=config.chromadb.collection_name,
            embedding_function=self._get_embedding_fn(),
            metadata={
                "hnsw:space": "cosine",
                "description": "PI AF element semantic search",
            },
        )
        return self._collection

    # ------------------------------------------------------------------ #
    # Indexing
    # ------------------------------------------------------------------ #

    def index_elements(
        self,
        elements: List[Dict[str, Any]],
        attributes_map: Dict[str, List[Dict[str, Any]]],
        batch_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Index all AF elements with their attributes into ChromaDB.

        Clears the existing collection first to avoid stale entries.
        Embeds documents in batches for memory efficiency.
        """
        t0 = time.monotonic()
        collection = self.get_or_create_collection()

        # Clear existing
        try:
            existing = collection.get(include=[])
            if existing["ids"]:
                collection.delete(ids=existing["ids"])
                logger.info("Cleared %d existing documents from collection", len(existing["ids"]))
        except Exception as exc:
            logger.warning("Could not clear collection: %s", exc)

        documents: List[str] = []
        ids: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        skipped = 0

        for elem in elements:
            webid = elem.get("WebId", elem.get("webid", ""))
            if not webid:
                skipped += 1
                continue
            attrs = attributes_map.get(webid, [])
            try:
                doc, elem_id, meta = _prepare_document(elem, attrs)
                documents.append(doc)
                ids.append(elem_id)
                metadatas.append(meta)
            except Exception as exc:
                logger.warning("Skipping element %s: %s", webid, exc)
                skipped += 1

        # Batch insert
        inserted = 0
        errors = 0
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i : i + batch_size]
            batch_ids = ids[i : i + batch_size]
            batch_meta = metadatas[i : i + batch_size]
            try:
                collection.upsert(documents=batch_docs, ids=batch_ids, metadatas=batch_meta)
                inserted += len(batch_docs)
                if (i // batch_size) % 5 == 0:
                    logger.info("ChromaDB indexed %d / %d elements …", inserted, len(documents))
            except Exception as exc:
                logger.error("Batch insert error (batch %d): %s", i // batch_size, exc)
                errors += 1

        self._indexed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        elapsed = round(time.monotonic() - t0, 2)
        logger.info(
            "ChromaDB indexing complete: %d indexed, %d skipped, %d batch errors in %.1f s",
            inserted, skipped, errors, elapsed,
        )
        return {
            "success": errors == 0,
            "indexed": inserted,
            "skipped": skipped,
            "errors": errors,
            "indexed_at": self._indexed_at,
            "elapsed_seconds": elapsed,
        }

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #

    def search(
        self,
        query: str,
        n_results: int = 10,
        where: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search with optional metadata filter.

        Applies the BGE instruction prefix to the query for higher quality
        retrieval; documents were embedded without prefix.
        """
        collection = self.get_or_create_collection()
        expanded = expand_query(query)
        prefixed_query = f"{_QUERY_PREFIX}{expanded}"

        try:
            results = collection.query(
                query_texts=[prefixed_query],
                n_results=min(n_results, max(1, collection.count())),
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.warning("Vector search failed (%s), falling back to metadata scan", exc)
            return self._metadata_scan(n_results, where)

        hits: List[Dict[str, Any]] = []
        for i, doc_id in enumerate(results["ids"][0]):
            meta = (results["metadatas"][0][i] or {})
            distance = results["distances"][0][i]
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            similarity = max(0.0, 1.0 - distance / 2.0)
            hits.append({
                "id": doc_id,
                "webid": meta.get("webid", ""),
                "name": meta.get("name", ""),
                "path": meta.get("path", ""),
                "template": meta.get("template", ""),
                "depth": meta.get("depth", 0),
                "has_children": meta.get("has_children", False),
                "attribute_count": meta.get("attribute_count", 0),
                "measurement_types": json.loads(meta.get("measurement_types", "[]")),
                "attribute_names": json.loads(meta.get("attribute_names", "[]")),
                "similarity": round(similarity, 4),
                "document_preview": (results["documents"][0][i] or "")[:200],
            })
        return hits

    def _metadata_scan(
        self,
        n_results: int,
        where: Optional[Dict],
    ) -> List[Dict[str, Any]]:
        """Fallback: return elements by metadata filter only (no vector ranking)."""
        collection = self.get_or_create_collection()
        try:
            kwargs: Dict[str, Any] = {"include": ["metadatas"], "limit": n_results}
            if where:
                kwargs["where"] = where
            results = collection.get(**kwargs)
        except Exception as exc:
            logger.error("Metadata scan also failed: %s", exc)
            return []

        hits: List[Dict[str, Any]] = []
        for i, meta in enumerate(results.get("metadatas") or []):
            meta = meta or {}
            hits.append({
                "id": results["ids"][i],
                "webid": meta.get("webid", ""),
                "name": meta.get("name", ""),
                "path": meta.get("path", ""),
                "template": meta.get("template", ""),
                "depth": meta.get("depth", 0),
                "similarity": 0.0,
                "measurement_types": json.loads(meta.get("measurement_types", "[]")),
            })
        return hits

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def get_stats(self) -> Dict[str, Any]:
        try:
            collection = self.get_or_create_collection()
            count = collection.count()
            return {
                "status": "ok",
                "collection": config.chromadb.collection_name,
                "document_count": count,
                "indexed_at": self._indexed_at,
                "embedding_model": config.embedding.model,
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def health_check(self) -> Dict[str, Any]:
        try:
            t0 = time.monotonic()
            results = self.search("gas separator pressure temperature", n_results=1)
            elapsed_ms = round((time.monotonic() - t0) * 1000)
            return {
                "status": "ok" if results else "empty",
                "search_latency_ms": elapsed_ms,
                "document_count": self.get_or_create_collection().count(),
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def should_refresh(self) -> bool:
        """True if index has never been built or is older than refresh interval."""
        if self._indexed_at is None:
            return True
        try:
            import datetime
            last = datetime.datetime.strptime(self._indexed_at, "%Y-%m-%dT%H:%M:%SZ")
            age_h = (datetime.datetime.utcnow() - last).total_seconds() / 3600
            return age_h >= config.indexing.refresh_hours
        except Exception:
            return True


# Module-level singleton
_vdb: Optional[VectorDBManager] = None


def get_vector_db() -> VectorDBManager:
    global _vdb
    if _vdb is None:
        _vdb = VectorDBManager()
    return _vdb

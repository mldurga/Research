"""
Coordinated indexing pipeline.

Runs once at startup (and on a 24h refresh cycle) to:
  1. Fetch all AF elements from PI Web API
  2. Fetch attributes for every element (concurrent, semaphore-capped)
  3. Build the NetworkX knowledge graph
  4. Build the ChromaDB vector index
  5. Build the BM25 keyword index
  6. Populate the alias map in the hybrid resolver

All three indexes share the same API fetch, so we pay the PI Web API
cost exactly once per indexing cycle.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from bm25_index import BM25Index
from config import config
from hybrid_resolver import HybridResolver
from knowledge_graph import AFKnowledgeGraph
from pi_client import PIWebAPIClient
from vector_db import VectorDBManager

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# AF hierarchy fetch
# --------------------------------------------------------------------------- #

async def _resolve_database_webid(client: PIWebAPIClient) -> str:
    """Return the WebId of the configured AF database."""
    servers = await client.get_af_servers()
    target_server = config.pi.af_server
    server_webid: Optional[str] = None

    for s in servers:
        if s.get("Name", "").lower() == target_server.lower():
            server_webid = s.get("WebId")
            break

    if not server_webid:
        if servers:
            server_webid = servers[0]["WebId"]
            logger.warning(
                "AF server '%s' not found; using first server '%s'",
                target_server, servers[0].get("Name"),
            )
        else:
            raise RuntimeError("No AF servers found in PI Web API")

    databases = await client.get_af_databases(server_webid)
    target_db = config.pi.af_database

    for db in databases:
        if db.get("Name", "").lower() == target_db.lower():
            return db["WebId"]

    if databases:
        db_webid = databases[0]["WebId"]
        logger.warning(
            "AF database '%s' not found; using first database '%s'",
            target_db, databases[0].get("Name"),
        )
        return db_webid

    raise RuntimeError("No AF databases found in PI Web API")


async def fetch_all_elements(client: PIWebAPIClient) -> List[Dict[str, Any]]:
    """
    Fetch the flat list of AF elements to be indexed.

    Behaviour depends on config.indexing.root_paths:
      - empty  → index the entire AF database (whole-database mode)
      - non-empty → index only the configured root subtrees. Each root path
        is resolved to its element, and that element plus its full descendant
        tree are included. Multiple roots are unioned and de-duplicated.
    """
    root_paths = config.indexing.root_paths

    if not root_paths:
        database_webid = await _resolve_database_webid(client)
        elements = await client.search_elements(
            database_webid=database_webid,
            query="*",
            max_count=config.indexing.max_elements,
        )
        logger.info("Fetched %d AF elements (whole-database mode)", len(elements))
        return elements

    return await _fetch_scoped_elements(client, root_paths)


async def _fetch_scoped_elements(
    client: PIWebAPIClient,
    root_paths: List[str],
) -> List[Dict[str, Any]]:
    """
    Fetch elements scoped to one or more root subtrees.
    Each root element is included along with its full descendant hierarchy.
    Results are merged and de-duplicated by WebId.
    """
    merged: Dict[str, Dict[str, Any]] = {}

    for path in root_paths:
        root = await client.get_element_by_path(path)
        if not root or not root.get("WebId"):
            logger.warning("Root path not found, skipping: %s", path)
            continue

        root_webid = root["WebId"]
        merged[root_webid] = root  # include the root element itself

        descendants = await client.search_descendants(
            root_webid,
            max_count=config.indexing.max_elements,
        )
        for d in descendants:
            webid = d.get("WebId")
            if webid:
                merged[webid] = d

        logger.info(
            "Scoped root '%s' (%s): %d descendants",
            root.get("Name", path), path, len(descendants),
        )

    if not merged:
        logger.error(
            "No elements resolved from INDEX_ROOT_PATHS=%s — check the paths",
            root_paths,
        )

    logger.info(
        "Fetched %d AF elements (scoped to %d root subtree(s))",
        len(merged), len(root_paths),
    )
    return list(merged.values())


# --------------------------------------------------------------------------- #
# Attribute fetch (concurrent)
# --------------------------------------------------------------------------- #

async def fetch_all_attributes(
    client: PIWebAPIClient,
    elements: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetch attributes for all elements concurrently.
    Uses a semaphore to cap parallel connections at config.indexing.concurrency.
    Returns {element_webid: [attribute_dicts]}.
    """
    webids = [e["WebId"] for e in elements if e.get("WebId")]
    logger.info(
        "Fetching attributes for %d elements (concurrency=%d) …",
        len(webids), config.indexing.concurrency,
    )
    t0 = time.monotonic()
    result = await client.batch_get_attributes(
        webids, concurrency=config.indexing.concurrency
    )
    total_attrs = sum(len(v) for v in result.values())
    elapsed = round(time.monotonic() - t0, 1)
    logger.info(
        "Attribute fetch complete: %d attributes for %d elements in %.1f s",
        total_attrs, len(result), elapsed,
    )
    return result


# --------------------------------------------------------------------------- #
# Full pipeline
# --------------------------------------------------------------------------- #

async def run_indexing_pipeline(
    client: PIWebAPIClient,
    graph: AFKnowledgeGraph,
    vector_db: VectorDBManager,
    bm25: BM25Index,
    resolver: HybridResolver,
) -> Dict[str, Any]:
    """
    Execute the full indexing cycle.

    Returns a result dict with per-component status and timing.
    Raises on unrecoverable errors (caller decides retry strategy).
    """
    pipeline_start = time.monotonic()
    result: Dict[str, Any] = {
        "success": False,
        "elements_fetched": 0,
        "attributes_fetched": 0,
        "graph": {},
        "vector_db": {},
        "bm25": {},
        "total_elapsed_seconds": 0.0,
    }

    # --- Step 1: Fetch elements ------------------------------------------
    logger.info("=== Indexing pipeline started ===")
    elements = await fetch_all_elements(client)
    result["elements_fetched"] = len(elements)

    if not elements:
        logger.error("No elements returned from PI Web API — aborting indexing")
        return result

    # --- Step 2: Fetch attributes ----------------------------------------
    attributes_map = await fetch_all_attributes(client, elements)
    result["attributes_fetched"] = sum(len(v) for v in attributes_map.values())

    # Merge attributes into element dicts for BM25 (graph/vector do it themselves)
    elements_with_attrs = []
    for elem in elements:
        e = dict(elem)
        e["attributes"] = attributes_map.get(elem.get("WebId", ""), [])
        # Normalise field names to lowercase for downstream consumers
        e.setdefault("webid", e.pop("WebId", ""))
        e.setdefault("name", e.pop("Name", ""))
        e.setdefault("description", e.pop("Description", ""))
        e.setdefault("path", e.pop("Path", ""))
        e.setdefault("template", e.pop("TemplateName", ""))
        e.setdefault("has_children", e.pop("HasChildren", False))
        # Re-add capitalised versions for components that expect them
        e["WebId"] = e["webid"]
        e["Name"] = e["name"]
        e["Description"] = e["description"]
        e["Path"] = e["path"]
        e["TemplateName"] = e["template"]
        e["HasChildren"] = e["has_children"]
        elements_with_attrs.append(e)

    # --- Step 3: Build knowledge graph -----------------------------------
    t3 = time.monotonic()
    try:
        # Pass original elements + attributes_map using original WebId keys
        orig_webid_map = {e.get("WebId") or e.get("webid"): e for e in elements_with_attrs}
        graph.build(list(orig_webid_map.values()), attributes_map)
        graph.save()
        result["graph"] = {
            "success": True,
            "node_count": graph.get_stats()["node_count"],
            "elapsed_seconds": round(time.monotonic() - t3, 2),
        }
    except Exception as exc:
        logger.error("Knowledge graph build failed: %s", exc, exc_info=True)
        result["graph"] = {"success": False, "error": str(exc)}

    # --- Step 4: Build vector DB -----------------------------------------
    t4 = time.monotonic()
    try:
        vdb_result = vector_db.index_elements(
            elements=elements_with_attrs,
            attributes_map=attributes_map,
            batch_size=config.indexing.batch_size,
        )
        result["vector_db"] = {**vdb_result, "elapsed_seconds": round(time.monotonic() - t4, 2)}
    except Exception as exc:
        logger.error("ChromaDB indexing failed: %s", exc, exc_info=True)
        result["vector_db"] = {"success": False, "error": str(exc)}

    # --- Step 5: Build BM25 index ----------------------------------------
    t5 = time.monotonic()
    try:
        bm25.build(elements_with_attrs)
        bm25.save()
        result["bm25"] = {
            "success": True,
            "document_count": bm25.get_stats()["document_count"],
            "elapsed_seconds": round(time.monotonic() - t5, 2),
        }
    except Exception as exc:
        logger.error("BM25 index build failed: %s", exc, exc_info=True)
        result["bm25"] = {"success": False, "error": str(exc)}

    # --- Step 6: Populate alias map --------------------------------------
    try:
        alias_count = resolver.build_alias_map()
        result["alias_map_entries"] = alias_count
    except Exception as exc:
        logger.warning("Alias map build failed: %s", exc)

    result["total_elapsed_seconds"] = round(time.monotonic() - pipeline_start, 2)
    result["success"] = (
        result["graph"].get("success", False)
        and result["vector_db"].get("success", False)
        and result["bm25"].get("success", False)
    )
    logger.info(
        "=== Indexing pipeline %s in %.1f s ===",
        "COMPLETE" if result["success"] else "COMPLETED WITH ERRORS",
        result["total_elapsed_seconds"],
    )
    return result


# --------------------------------------------------------------------------- #
# Background refresh loop
# --------------------------------------------------------------------------- #

async def background_indexing_loop(
    client: PIWebAPIClient,
    graph: AFKnowledgeGraph,
    vector_db: VectorDBManager,
    bm25: BM25Index,
    resolver: HybridResolver,
    state: Dict[str, Any],
) -> None:
    """
    Async task that runs indefinitely, triggering re-indexing every
    config.indexing.refresh_hours hours.  Errors are logged and the loop
    backs off for 30 minutes before retrying.
    """
    refresh_seconds = config.indexing.refresh_hours * 3600

    while True:
        if not state.get("indexing_in_progress"):
            state["indexing_in_progress"] = True
            state["last_error"] = None
            try:
                pipeline_result = await run_indexing_pipeline(
                    client, graph, vector_db, bm25, resolver
                )
                state["last_pipeline_result"] = pipeline_result
                state["indexed_elements_count"] = pipeline_result.get("elements_fetched", 0)
                state["initialization_complete"] = True
            except Exception as exc:
                logger.error("Indexing pipeline failed: %s", exc, exc_info=True)
                state["last_error"] = str(exc)
                await asyncio.sleep(1800)  # 30-minute backoff on failure
            finally:
                state["indexing_in_progress"] = False

        await asyncio.sleep(refresh_seconds)

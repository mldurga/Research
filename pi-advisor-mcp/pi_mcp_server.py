"""
PI Advisor MCP Server — Panorama

Tool catalogue (15 tools):
  Data retrieval:
    get_current_value          — single attribute current value (fast path)
    get_recorded_values        — historical time-series
    get_interpolated_values    — regular-interval time-series
    get_stream_summary         — statistical summary over time range
    get_streamset_values       — all current attribute values for an element
    batch_get_current_values   — current values for multiple attributes concurrently

  Element search:
    search_elements            — PI Web API attribute/template query
    search_elements_semantic   — hybrid (BM25 + vector + alias) search
    resolve_element_attribute  — resolve a natural language query to element+attribute WebIds

  Knowledge graph:
    get_graph_context          — element info + ancestors + children from graph
    get_impact_analysis        — what breaks if this equipment goes offline
    get_investigation_context  — RCA context: element + siblings + ancestors
    find_instruments           — instruments/sensors within a subtree
    compare_siblings           — list peer elements for comparative analysis

  System:
    get_system_health          — full health check across all components
    trigger_reindex            — manual reindex trigger

Performance design:
  - Every request checks the TTL cache first (hit → <1 ms)
  - Natural language queries go through the hybrid resolver (50-150 ms)
    BEFORE any LLM call, returning WebIds for direct PI API calls
  - Knowledge graph queries are in-memory (< 1 ms)
  - selectedFields on all PI API calls (40-70% smaller payloads)
  - Batch/concurrent PI calls for multi-element operations
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

from bm25_index import get_bm25_index
from cache import TTL, TTLCache, get_cache
from config import config
from hybrid_resolver import HybridResolver, extract_metric, get_resolver
from indexing_pipeline import background_indexing_loop
from knowledge_graph import AFKnowledgeGraph, get_graph
from pi_client import PIWebAPIClient, close_client, get_client
from vector_db import VectorDBManager, get_vector_db

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #

logging.basicConfig(
    level=getattr(logging, config.log_level, logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("pi_advisor")

# --------------------------------------------------------------------------- #
# Server state
# --------------------------------------------------------------------------- #

_state: Dict[str, Any] = {
    "initialization_complete": False,
    "indexing_in_progress": False,
    "indexed_elements_count": 0,
    "last_error": None,
    "startup_time": datetime.utcnow().isoformat(),
    "last_pipeline_result": None,
}

# --------------------------------------------------------------------------- #
# MCP server instance
# --------------------------------------------------------------------------- #

mcp = FastMCP(
    name="pi-advisor",
    instructions=(
        "You are an AI assistant with access to an AVEVA PI System via PI Web API. "
        "Use the resolve_element_attribute tool FIRST for natural language queries "
        "to obtain element and attribute WebIds before calling data retrieval tools. "
        "Always prefer batch tools over sequential single-item calls. "
        "Knowledge graph tools answer structural questions without hitting PI Web API."
    ),
)

# --------------------------------------------------------------------------- #
# Lazy singletons (initialised during server startup)
# --------------------------------------------------------------------------- #

def _client() -> PIWebAPIClient:
    return get_client()

def _graph() -> AFKnowledgeGraph:
    return get_graph()

def _resolver() -> HybridResolver:
    return get_resolver()

def _cache() -> TTLCache:
    return get_cache()

def _vdb() -> VectorDBManager:
    return get_vector_db()


# =========================================================================== #
# TOOLS
# =========================================================================== #

# --------------------------------------------------------------------------- #
# 1. get_current_value
# --------------------------------------------------------------------------- #

@mcp.tool()
async def get_current_value(
    attribute_webid: str,
    element_name: str = "",
    attribute_name: str = "",
) -> Dict[str, Any]:
    """
    Get the current (latest) value for a single PI attribute.

    Parameters
    ----------
    attribute_webid : str
        WebId of the PI attribute (obtain via resolve_element_attribute).
    element_name : str
        Human-readable element name for context in the response.
    attribute_name : str
        Human-readable attribute name for context.

    Returns dict with Timestamp, Value, UnitsAbbreviation, Good flag.
    Cached for 30 seconds.
    """
    cache_key = TTLCache.make_key("get_current_value", {"webid": attribute_webid})
    cached = await _cache().get(cache_key)
    if cached:
        return {**cached, "_from_cache": True}

    try:
        data = await _client().get_stream_value(attribute_webid)
        result = {
            "element": element_name,
            "attribute": attribute_name,
            "webid": attribute_webid,
            "timestamp": data.get("Timestamp", ""),
            "value": data.get("Value"),
            "units": data.get("UnitsAbbreviation", ""),
            "good": data.get("Good", True),
            "_from_cache": False,
        }
        await _cache().set(cache_key, result, TTL.CURRENT_VALUE)
        return result
    except Exception as exc:
        return {"error": str(exc), "webid": attribute_webid}


# --------------------------------------------------------------------------- #
# 2. get_recorded_values
# --------------------------------------------------------------------------- #

@mcp.tool()
async def get_recorded_values(
    attribute_webid: str,
    start_time: str = "*-1d",
    end_time: str = "*",
    max_count: int = 1000,
) -> Dict[str, Any]:
    """
    Retrieve recorded (compressed) historical values for a PI attribute.

    Parameters
    ----------
    attribute_webid : str   WebId of the attribute.
    start_time      : str   PI time string e.g. '*-7d', '2024-01-01T00:00:00Z'.
    end_time        : str   PI time string, default '*' (now).
    max_count       : int   Max values to return (capped at 10 000).
    """
    max_count = min(max_count, 10_000)
    try:
        items = await _client().get_stream_recorded(
            attribute_webid,
            start_time=start_time,
            end_time=end_time,
            max_count=max_count,
        )
        good_items = [i for i in items if i.get("Good", True)]
        return {
            "webid": attribute_webid,
            "start_time": start_time,
            "end_time": end_time,
            "total_points": len(items),
            "good_points": len(good_items),
            "values": items,
        }
    except Exception as exc:
        return {"error": str(exc), "webid": attribute_webid}


# --------------------------------------------------------------------------- #
# 3. get_interpolated_values
# --------------------------------------------------------------------------- #

@mcp.tool()
async def get_interpolated_values(
    attribute_webid: str,
    start_time: str = "*-1d",
    end_time: str = "*",
    interval: str = "1h",
) -> Dict[str, Any]:
    """
    Retrieve regularly-spaced interpolated values for a PI attribute.

    Parameters
    ----------
    attribute_webid : str   WebId of the attribute.
    start_time      : str   Start of range.
    end_time        : str   End of range.
    interval        : str   Interval string e.g. '1h', '15m', '30s'.
    """
    try:
        items = await _client().get_stream_interpolated(
            attribute_webid,
            start_time=start_time,
            end_time=end_time,
            interval=interval,
        )
        return {
            "webid": attribute_webid,
            "start_time": start_time,
            "end_time": end_time,
            "interval": interval,
            "point_count": len(items),
            "values": items,
        }
    except Exception as exc:
        return {"error": str(exc), "webid": attribute_webid}


# --------------------------------------------------------------------------- #
# 4. get_stream_summary
# --------------------------------------------------------------------------- #

@mcp.tool()
async def get_stream_summary(
    attribute_webid: str,
    start_time: str = "*-1d",
    end_time: str = "*",
    summary_types: str = "Average,Minimum,Maximum,StdDev",
) -> Dict[str, Any]:
    """
    Statistical summary (Average, Min, Max, StdDev) for a PI attribute.

    Parameters
    ----------
    attribute_webid : str   WebId of the attribute.
    start_time      : str   Start of range.
    end_time        : str   End of range.
    summary_types   : str   Comma-separated: Average,Minimum,Maximum,StdDev,Count.
    """
    cache_key = TTLCache.make_key(
        "get_stream_summary",
        {"webid": attribute_webid, "start": start_time, "end": end_time, "types": summary_types},
    )
    cached = await _cache().get(cache_key)
    if cached:
        return {**cached, "_from_cache": True}

    try:
        items = await _client().get_stream_summary(
            attribute_webid,
            start_time=start_time,
            end_time=end_time,
            summary_types=summary_types,
        )
        summary: Dict[str, Any] = {item["Type"]: item.get("Value", {}) for item in items}
        result = {
            "webid": attribute_webid,
            "start_time": start_time,
            "end_time": end_time,
            "summary": summary,
            "_from_cache": False,
        }
        await _cache().set(cache_key, result, TTL.SUMMARY)
        return result
    except Exception as exc:
        return {"error": str(exc), "webid": attribute_webid}


# --------------------------------------------------------------------------- #
# 5. get_streamset_values
# --------------------------------------------------------------------------- #

@mcp.tool()
async def get_streamset_values(
    element_webid: str,
    name_filter: str = "*",
) -> Dict[str, Any]:
    """
    Get current values for ALL attributes of an AF element in a single API call.

    More efficient than calling get_current_value repeatedly.

    Parameters
    ----------
    element_webid : str   WebId of the AF element.
    name_filter   : str   Wildcard filter on attribute name (default: '*' = all).
    """
    cache_key = TTLCache.make_key("get_streamset_values", {"webid": element_webid, "filter": name_filter})
    cached = await _cache().get(cache_key)
    if cached:
        return {**cached, "_from_cache": True}

    try:
        items = await _client().get_streamset_current(element_webid, name_filter=name_filter)
        result = {
            "element_webid": element_webid,
            "attribute_count": len(items),
            "attributes": items,
            "_from_cache": False,
        }
        await _cache().set(cache_key, result, TTL.CURRENT_VALUE)
        return result
    except Exception as exc:
        return {"error": str(exc), "element_webid": element_webid}


# --------------------------------------------------------------------------- #
# 6. batch_get_current_values
# --------------------------------------------------------------------------- #

@mcp.tool()
async def batch_get_current_values(
    attribute_webids: List[str],
) -> Dict[str, Any]:
    """
    Fetch current values for multiple attribute WebIds concurrently.

    Use this instead of calling get_current_value in a loop.
    Returns a dict keyed by WebId.

    Parameters
    ----------
    attribute_webids : list[str]   List of attribute WebIds (max 50).
    """
    attribute_webids = attribute_webids[:50]
    cache_key = TTLCache.make_key("batch_get_current_values", {"webids": sorted(attribute_webids)})
    cached = await _cache().get(cache_key)
    if cached:
        return {**cached, "_from_cache": True}

    try:
        values = await _client().batch_get_stream_values(attribute_webids)
        result = {
            "requested": len(attribute_webids),
            "succeeded": sum(1 for v in values.values() if v is not None),
            "values": values,
            "_from_cache": False,
        }
        await _cache().set(cache_key, result, TTL.CURRENT_VALUE)
        return result
    except Exception as exc:
        return {"error": str(exc)}


# --------------------------------------------------------------------------- #
# 7. search_elements
# --------------------------------------------------------------------------- #

@mcp.tool()
async def search_elements(
    query: str = "*",
    template_name: str = "",
    max_results: int = 50,
) -> Dict[str, Any]:
    """
    Search AF elements via PI Web API attribute syntax.

    Examples: query='Name:=GS-*', query='Name:=*separator*'.
    Use search_elements_semantic for natural language queries.

    Parameters
    ----------
    query        : str   PI search query syntax.
    template_name: str   Filter by AF template name (optional).
    max_results  : int   Max elements to return (capped at 200).
    """
    max_results = min(max_results, 200)
    cache_key = TTLCache.make_key("search_elements", {"q": query, "t": template_name, "n": max_results})
    cached = await _cache().get(cache_key)
    if cached:
        return {**cached, "_from_cache": True}

    try:
        from indexing_pipeline import _resolve_database_webid
        db_webid = await _resolve_database_webid(_client())
        items = await _client().search_elements(
            database_webid=db_webid,
            query=query,
            template_name=template_name,
            max_count=max_results,
        )
        result = {
            "query": query,
            "template_filter": template_name,
            "count": len(items),
            "elements": items,
            "_from_cache": False,
        }
        await _cache().set(cache_key, result, TTL.STRUCTURAL)
        return result
    except Exception as exc:
        return {"error": str(exc), "query": query}


# --------------------------------------------------------------------------- #
# 8. search_elements_semantic
# --------------------------------------------------------------------------- #

@mcp.tool()
async def search_elements_semantic(
    query: str,
    n_results: int = 10,
    template_filter: str = "",
) -> Dict[str, Any]:
    """
    Semantic + keyword hybrid search for AF elements using natural language.

    Combines BM25, vector similarity, and alias lookup for best recall on
    PI naming conventions (abbreviations, ISA codes, domain synonyms).

    Parameters
    ----------
    query           : str   Natural language description of the asset.
    n_results       : int   Number of candidates to return (max 20).
    template_filter : str   Optional template name substring filter.
    """
    n_results = min(n_results, 20)
    cache_key = TTLCache.make_key("search_elements_semantic", {"q": query, "n": n_results, "t": template_filter})
    cached = await _cache().get(cache_key)
    if cached:
        return {**cached, "_from_cache": True}

    try:
        matches = _resolver().resolve_elements(query, top_k=n_results)
        elements: List[Dict[str, Any]] = []
        for m in matches:
            elem = m.to_dict()
            if template_filter and template_filter.lower() not in m.template.lower():
                continue
            # Enrich with graph data if available
            node = _graph().get_node(m.webid)
            if node:
                elem["attribute_count"] = len(node.get("attributes", []))
                elem["measurement_types"] = list(node.get("measurement_types", set()))
            elements.append(elem)

        result = {
            "query": query,
            "count": len(elements),
            "elements": elements,
            "_from_cache": False,
        }
        await _cache().set(cache_key, result, TTL.RESOLUTION)
        return result
    except Exception as exc:
        return {"error": str(exc), "query": query}


# --------------------------------------------------------------------------- #
# 9. resolve_element_attribute  ← KEY TOOL for fast responses
# --------------------------------------------------------------------------- #

@mcp.tool()
async def resolve_element_attribute(
    query: str,
    metric_hint: str = "",
    top_k: int = 3,
) -> Dict[str, Any]:
    """
    ALWAYS CALL THIS FIRST for natural language PI queries.

    Resolves a natural language query to concrete element and attribute WebIds
    that can be passed directly to data retrieval tools.  Runs in 50-150 ms
    using only in-memory indexes (no PI Web API call).

    Parameters
    ----------
    query      : str   Natural language query, e.g. "temperature at gas sep Train 2".
    metric_hint: str   Override automatic metric detection. One of:
                       temperature, pressure, flow, level, vibration, speed,
                       power, health, status, production, efficiency.
    top_k      : int   Number of element candidates to return (1-5).

    Returns a list of candidates, each with element_webid, attribute_webid,
    attribute_name, and a confidence score.  Use the top candidate.
    """
    cache_key = TTLCache.make_key("resolve_element_attribute", {"q": query, "m": metric_hint, "k": top_k})
    cached = await _cache().get(cache_key)
    if cached:
        return {**cached, "_from_cache": True}

    metric = metric_hint or extract_metric(query) or ""
    results = _resolver().resolve_all(query, metric_hint=metric or None, top_k=min(top_k, 5))

    candidates: List[Dict[str, Any]] = []
    for r in results:
        c: Dict[str, Any] = r.element.to_dict()
        if r.attribute:
            c["attribute_webid"] = r.attribute.get("WebId") or r.attribute.get("webid", "")
            c["attribute_name"] = r.attribute.get("Name") or r.attribute.get("name", "")
            c["attribute_units"] = r.attribute.get("DefaultUnitsName", "")
            c["attribute_type"] = r.attribute.get("Type", "")
        else:
            c["attribute_webid"] = ""
            c["attribute_name"] = ""
            c["attribute_units"] = ""
        candidates.append(c)

    result = {
        "query": query,
        "detected_metric": metric,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "ready_for_api": bool(candidates and candidates[0].get("attribute_webid")),
        "_from_cache": False,
    }
    await _cache().set(cache_key, result, TTL.RESOLUTION)
    return result


# --------------------------------------------------------------------------- #
# 10. get_graph_context
# --------------------------------------------------------------------------- #

@mcp.tool()
async def get_graph_context(
    element_webid: str,
    include_children: bool = True,
    include_ancestors: bool = True,
    include_attributes: bool = True,
) -> Dict[str, Any]:
    """
    Retrieve the structural context of an AF element from the knowledge graph.
    Sub-millisecond response — does NOT call PI Web API.

    Parameters
    ----------
    element_webid     : str    WebId of the element.
    include_children  : bool   Include direct child elements.
    include_ancestors : bool   Include parent chain up to root.
    include_attributes: bool   Include attribute list.
    """
    cache_key = TTLCache.make_key("get_graph_context", {
        "webid": element_webid, "ch": include_children,
        "an": include_ancestors, "at": include_attributes,
    })
    cached = await _cache().get(cache_key)
    if cached:
        return {**cached, "_from_cache": True}

    node = _graph().get_node(element_webid)
    if not node:
        return {"error": f"Element {element_webid} not found in knowledge graph"}

    response: Dict[str, Any] = {
        "element_webid": element_webid,
        "name": node.get("name", ""),
        "path": node.get("path", ""),
        "template": node.get("template", ""),
        "description": node.get("description", ""),
        "depth": node.get("depth", 0),
        "is_leaf": node.get("is_leaf", False),
        "measurement_types": list(node.get("measurement_types", set())),
        "_from_cache": False,
    }

    if include_attributes:
        attrs = _graph().get_element_attributes(element_webid)
        response["attributes"] = [
            {k: v for k, v in a.items() if k in ("Name", "WebId", "Type", "DefaultUnitsName", "DataReference")}
            for a in attrs
        ]

    if include_children:
        response["children"] = [
            {"webid": c["webid"], "name": c["name"], "template": c["template"]}
            for c in _graph().get_children(element_webid)
        ]

    if include_ancestors:
        response["ancestors"] = [
            {"webid": a["webid"], "name": a["name"], "depth": a["depth"]}
            for a in _graph().get_ancestors(element_webid)
        ]

    await _cache().set(cache_key, response, TTL.STRUCTURAL)
    return response


# --------------------------------------------------------------------------- #
# 11. get_impact_analysis
# --------------------------------------------------------------------------- #

@mcp.tool()
async def get_impact_analysis(element_webid: str) -> Dict[str, Any]:
    """
    What downstream elements and peer equipment are affected if this
    element goes offline?  Uses graph traversal — no PI Web API call.

    Useful for: shutdown planning, maintenance window impact assessment,
    "if we shut down K-101, what's affected?" queries.

    Parameters
    ----------
    element_webid : str   WebId of the equipment to analyse.
    """
    cache_key = TTLCache.make_key("get_impact_analysis", {"webid": element_webid})
    cached = await _cache().get(cache_key)
    if cached:
        return {**cached, "_from_cache": True}

    result = _graph().get_impact_analysis(element_webid)
    if "error" not in result:
        result["_from_cache"] = False
        await _cache().set(cache_key, result, TTL.STRUCTURAL)
    return result


# --------------------------------------------------------------------------- #
# 12. get_investigation_context
# --------------------------------------------------------------------------- #

@mcp.tool()
async def get_investigation_context(element_webid: str) -> Dict[str, Any]:
    """
    Root-cause analysis context for an anomaly at the given element.

    Returns: element attributes, parent chain, sibling elements,
    and child elements — everything needed to start an RCA without
    additional graph queries.

    Parameters
    ----------
    element_webid : str   WebId of the element showing the anomaly.
    """
    cache_key = TTLCache.make_key("get_investigation_context", {"webid": element_webid})
    cached = await _cache().get(cache_key)
    if cached:
        return {**cached, "_from_cache": True}

    result = _graph().get_investigation_context(element_webid)
    if "error" not in result:
        # Serialise measurement_types set
        if "element" in result:
            mt = result["element"].get("measurement_types", set())
            result["element"]["measurement_types"] = list(mt)
        result["_from_cache"] = False
        await _cache().set(cache_key, result, TTL.STRUCTURAL)
    return result


# --------------------------------------------------------------------------- #
# 13. find_instruments
# --------------------------------------------------------------------------- #

@mcp.tool()
async def find_instruments(
    element_webid: str,
    instrument_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Find all instrument / sensor elements within a subtree.

    Parameters
    ----------
    element_webid    : str         WebId of the root of the subtree.
    instrument_types : list[str]   Optional template name keywords to filter
                                   (e.g. ['Transmitter', 'Sensor', 'Analyzer']).
    """
    cache_key = TTLCache.make_key("find_instruments", {
        "webid": element_webid, "types": sorted(instrument_types or [])
    })
    cached = await _cache().get(cache_key)
    if cached:
        return {**cached, "_from_cache": True}

    instruments = _graph().find_instruments_in_subtree(element_webid, instrument_types)
    result = {
        "element_webid": element_webid,
        "type_filter": instrument_types,
        "instrument_count": len(instruments),
        "instruments": [
            {
                "webid": i["webid"],
                "name": i.get("name", ""),
                "path": i.get("path", ""),
                "template": i.get("template", ""),
                "measurement_types": list(i.get("measurement_types", set())),
            }
            for i in instruments
        ],
        "_from_cache": False,
    }
    await _cache().set(cache_key, result, TTL.STRUCTURAL)
    return result


# --------------------------------------------------------------------------- #
# 14. compare_siblings
# --------------------------------------------------------------------------- #

@mcp.tool()
async def compare_siblings(element_webid: str) -> Dict[str, Any]:
    """
    Return the reference element and all sibling elements (same parent).

    Use this to identify all elements of the same type for comparative
    analysis (e.g. all trains, all compressors in a section).
    After calling this, use batch_get_current_values to fetch their data.

    Parameters
    ----------
    element_webid : str   WebId of any element in the group.
    """
    cache_key = TTLCache.make_key("compare_siblings", {"webid": element_webid})
    cached = await _cache().get(cache_key)
    if cached:
        return {**cached, "_from_cache": True}

    comparison = _graph().compare_siblings(element_webid)
    if "error" not in comparison:
        comparison["_from_cache"] = False
        await _cache().set(cache_key, comparison, TTL.STRUCTURAL)
    return comparison


# --------------------------------------------------------------------------- #
# 15. get_system_health
# --------------------------------------------------------------------------- #

@mcp.tool()
async def get_system_health() -> Dict[str, Any]:
    """
    Comprehensive health check for all system components.
    Includes PI Web API connectivity, knowledge graph state, vector DB,
    BM25 index, cache stats, and indexing pipeline status.
    """
    cache_key = "system_health"
    cached = await _cache().get(cache_key)
    if cached:
        return {**cached, "_from_cache": True}

    health: Dict[str, Any] = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "server_state": {
            "initialization_complete": _state["initialization_complete"],
            "indexing_in_progress": _state["indexing_in_progress"],
            "indexed_elements_count": _state["indexed_elements_count"],
            "startup_time": _state["startup_time"],
            "last_error": _state.get("last_error"),
        },
        "_from_cache": False,
    }

    # PI Web API
    try:
        pi_health = await asyncio.wait_for(_client().test_connection(), timeout=5.0)
        health["pi_webapi"] = pi_health
    except Exception as exc:
        health["pi_webapi"] = {"ok": False, "error": str(exc)}

    # Knowledge graph
    health["knowledge_graph"] = _graph().get_stats()

    # Vector DB
    health["vector_db"] = _vdb().health_check()

    # BM25
    health["bm25"] = get_bm25_index().get_stats()

    # Cache
    health["cache"] = _cache().stats()

    # Overall status
    pi_ok = health["pi_webapi"].get("ok", False)
    graph_ok = health["knowledge_graph"].get("built", False)
    vdb_ok = health["vector_db"].get("status") == "ok"
    health["overall_status"] = "healthy" if (pi_ok and graph_ok and vdb_ok) else "degraded"

    await _cache().set(cache_key, health, TTL.HEALTH)
    return health


# --------------------------------------------------------------------------- #
# 16. trigger_reindex
# --------------------------------------------------------------------------- #

@mcp.tool()
async def trigger_reindex() -> Dict[str, Any]:
    """
    Manually trigger a full AF hierarchy reindex (graph + vector DB + BM25).

    Safe to call at any time — returns immediately if indexing is already
    running.  Otherwise starts indexing in the background.
    """
    if _state["indexing_in_progress"]:
        return {
            "started": False,
            "reason": "Indexing already in progress",
            "indexed_elements_count": _state["indexed_elements_count"],
        }

    async def _run():
        from indexing_pipeline import run_indexing_pipeline
        _state["indexing_in_progress"] = True
        try:
            result = await run_indexing_pipeline(
                _client(), _graph(), _vdb(), get_bm25_index(), _resolver()
            )
            _state["last_pipeline_result"] = result
            _state["indexed_elements_count"] = result.get("elements_fetched", 0)
            _state["initialization_complete"] = True
        except Exception as exc:
            _state["last_error"] = str(exc)
            logger.error("Manual reindex failed: %s", exc)
        finally:
            _state["indexing_in_progress"] = False

    asyncio.create_task(_run())
    return {
        "started": True,
        "message": "Reindex started in background. Check get_system_health for progress.",
    }


# =========================================================================== #
# RESOURCES
# =========================================================================== #

@mcp.resource("pi://system/status")
async def resource_system_status() -> str:
    """Quick system status snapshot."""
    pi_ok = False
    try:
        await asyncio.wait_for(_client().test_connection(), timeout=3.0)
        pi_ok = True
    except Exception:
        pass

    graph_stats = _graph().get_stats()
    return (
        f"PI Advisor Status\n"
        f"PI Web API: {'OK' if pi_ok else 'ERROR'}\n"
        f"Graph nodes: {graph_stats.get('node_count', 0)}\n"
        f"Indexed elements: {_state['indexed_elements_count']}\n"
        f"Cache hit rate: {_cache().stats().get('hit_rate', 0):.1%}\n"
        f"Initialized: {_state['initialization_complete']}\n"
    )


@mcp.resource("pi://graph/roots")
async def resource_graph_roots() -> str:
    """List of top-level AF elements (trains, areas, sites)."""
    import json
    roots = _graph().get_root_elements()
    return json.dumps(
        [{"webid": r["webid"], "name": r.get("name"), "template": r.get("template")} for r in roots],
        indent=2,
    )


# =========================================================================== #
# PROMPTS
# =========================================================================== #

@mcp.prompt()
def pi_query_guide() -> str:
    """Guide for efficient PI data retrieval."""
    return """
You are a PI System expert assistant for ADNOC Upstream operations.

## Efficient Query Workflow

1. **Always start with resolve_element_attribute** for natural language queries.
   This returns element_webid and attribute_webid in <150ms without an LLM call.

2. **For current values**: Use get_current_value (single) or batch_get_current_values (multiple).

3. **For structural questions** ("what's upstream", "what equipment is in Train 2"):
   Use get_graph_context — it's sub-millisecond, no PI API call needed.

4. **For comparisons** ("compare all trains"): Use compare_siblings → then batch_get_current_values.

5. **For RCA** ("why is Train 1 low?"): Use get_investigation_context → then fetch key attributes.

## Response Principles for Senior Leadership

- Lead with the KPI that answers the question directly.
- Use business units: MMscfd (gas), bbl/d (oil/condensate), % of target.
- Flag deviations > 5% from target or alarm conditions immediately.
- Summarise in 3-5 bullet points; offer to drill down.
- Never show raw PI timestamps — convert to "Today 09:30", "Yesterday 14:00".
"""


@mcp.prompt()
def executive_summary_format() -> str:
    """Format template for executive daily summary."""
    return """
## Production Summary — {date}

### Overall Status: {overall_status}

**Portfolio Performance**
| Asset | Production | Target | Status |
|-------|-----------|--------|--------|
{table_rows}

**Key Highlights**
{highlights}

**Actions Required**
{actions}

---
*Data as of {timestamp} | Source: PI System*
"""


# =========================================================================== #
# STARTUP
# =========================================================================== #

async def startup() -> None:
    """
    Non-blocking server startup:
      1. Test PI Web API connectivity.
      2. Try to load indexes from disk (fast restart).
      3. If disk cache is stale or missing, trigger full reindex in background.
    """
    logger.info("PI Advisor MCP server starting …")

    # Validate required configuration
    if not config.pi.url:
        logger.critical("PI_WEBAPI_URL is not set — cannot start server")
        sys.exit(1)

    # Test PI connectivity (don't block startup on failure)
    try:
        conn = await asyncio.wait_for(_client().test_connection(), timeout=10.0)
        logger.info("PI Web API connected: %s (%.0f ms)", conn.get("version"), conn.get("response_ms", 0))
    except Exception as exc:
        logger.warning("PI Web API not reachable at startup: %s (will retry during indexing)", exc)

    # Attempt to load indexes from disk
    graph_loaded = _graph().load()
    bm25_loaded = get_bm25_index().load()

    if graph_loaded:
        logger.info("Knowledge graph loaded from disk: %d nodes", _graph().get_stats()["node_count"])
        # Rebuild alias map from loaded graph
        _resolver().build_alias_map()

    if bm25_loaded:
        logger.info("BM25 index loaded from disk: %d documents", get_bm25_index().get_stats()["document_count"])

    disk_cache_ok = graph_loaded and bm25_loaded and not _vdb().should_refresh()
    if disk_cache_ok:
        logger.info("All indexes loaded from disk — skipping full reindex")
        _state["initialization_complete"] = True
        _state["indexed_elements_count"] = _graph().get_stats()["node_count"]
    else:
        logger.info("Starting background indexing pipeline …")

    # Always run the background loop (it will skip reindex if disk cache was fresh)
    asyncio.create_task(
        background_indexing_loop(
            _client(), _graph(), _vdb(), get_bm25_index(), _resolver(), _state
        )
    )

    logger.info("Server startup complete (initialization_complete=%s)", _state["initialization_complete"])


async def cleanup() -> None:
    logger.info("Shutting down PI Advisor MCP server …")
    await close_client()


# =========================================================================== #
# ENTRY POINT
# =========================================================================== #

if __name__ == "__main__":
    import asyncio

    async def _main() -> None:
        await startup()
        await mcp.run_async()
        await cleanup()

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass

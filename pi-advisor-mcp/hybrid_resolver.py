"""
3-layer hybrid AF element + attribute resolver.

Resolution pipeline (executed before any LLM call):

  Layer 1 — Alias map (exact / normalised match)
             Built at startup from element names and common abbreviations.
             Returns with confidence=1.0 on hit.

  Layer 2 — BM25 keyword search
             Tokenised, synonym-expanded query over element documents.
             Returns ranked list of (webid, bm25_score).

  Layer 3 — ChromaDB vector search
             Semantic similarity over BGE-embedded element documents.
             Returns ranked list of (webid, similarity_score).

Fusion:
  Reciprocal Rank Fusion (k=60) combines BM25 and vector rankings.
  Alias-matched candidates get a large additive bonus.

Attribute resolution:
  After element resolution, the metric mentioned in the query is matched
  against the element's attribute list using synonym expansion.
  Returns the attribute WebId ready for a direct PI Web API call.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from bm25_index import BM25Index
from knowledge_graph import AFKnowledgeGraph
from synonyms import expand_query, get_aliases, get_measurement_type
from vector_db import VectorDBManager

logger = logging.getLogger(__name__)

RRF_K = 60      # Standard constant for Reciprocal Rank Fusion
ALIAS_BONUS = 3.0  # Additive bonus to RRF score for alias-matched elements


# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #

class ElementMatch:
    __slots__ = ("webid", "name", "path", "template", "score", "match_layer")

    def __init__(
        self,
        webid: str,
        name: str,
        path: str,
        template: str,
        score: float,
        match_layer: str,
    ) -> None:
        self.webid = webid
        self.name = name
        self.path = path
        self.template = template
        self.score = score
        self.match_layer = match_layer

    def to_dict(self) -> Dict[str, Any]:
        return {
            "webid": self.webid,
            "name": self.name,
            "path": self.path,
            "template": self.template,
            "score": round(self.score, 4),
            "match_layer": self.match_layer,
        }


class ResolutionResult:
    """Full resolution outcome: element + optional attribute."""

    def __init__(
        self,
        element: ElementMatch,
        attribute: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.element = element
        self.attribute = attribute   # attribute dict from graph node or None

    @property
    def element_webid(self) -> str:
        return self.element.webid

    @property
    def attribute_webid(self) -> Optional[str]:
        return (self.attribute or {}).get("WebId") or (self.attribute or {}).get("webid")

    @property
    def attribute_name(self) -> Optional[str]:
        return (self.attribute or {}).get("Name") or (self.attribute or {}).get("name")

    def to_dict(self) -> Dict[str, Any]:
        d = {"element": self.element.to_dict()}
        if self.attribute:
            d["attribute"] = self.attribute
        return d


# --------------------------------------------------------------------------- #
# Resolver
# --------------------------------------------------------------------------- #

class HybridResolver:
    """
    Stateless resolver that holds references to the three search layers.
    Call ``resolve()`` for full element + attribute resolution.
    Call ``resolve_elements_only()`` when attribute resolution isn't needed.
    """

    def __init__(
        self,
        bm25: BM25Index,
        vector_db: VectorDBManager,
        graph: AFKnowledgeGraph,
    ) -> None:
        self._bm25 = bm25
        self._vdb = vector_db
        self._graph = graph
        self._alias_map: Dict[str, str] = {}   # normalised text → webid

    # ------------------------------------------------------------------ #
    # Alias map management
    # ------------------------------------------------------------------ #

    def build_alias_map(self) -> int:
        """
        Populate the alias map from graph node names and path leaf names.
        Called automatically by the indexing pipeline after graph build.
        Returns the number of entries added.
        """
        self._alias_map.clear()
        for webid, data in self._graph.all_elements():
            name = data.get("name", "")
            if name:
                self._alias_map[name.lower()] = webid
                # Also index the path leaf (last component)
                path = data.get("path", "")
                if path:
                    leaf = path.rsplit("\\", 1)[-1]
                    if leaf.lower() not in self._alias_map:
                        self._alias_map[leaf.lower()] = webid
        logger.info("Alias map built: %d entries", len(self._alias_map))
        return len(self._alias_map)

    # ------------------------------------------------------------------ #
    # Element resolution
    # ------------------------------------------------------------------ #

    def resolve_elements(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[ElementMatch]:
        """
        Return the top-k element matches for a natural language query.
        Combines BM25, vector search, and alias lookup via RRF.
        """
        if not self._graph.is_built:
            logger.warning("Knowledge graph not built — skipping graph-aided resolution")

        # --- Layer 1: alias lookup ----------------------------------------
        alias_hits: Dict[str, float] = {}
        q_lower = query.lower()
        for alias, webid in self._alias_map.items():
            if alias in q_lower:
                alias_hits[webid] = ALIAS_BONUS

        # --- Layer 2: BM25 keyword search ---------------------------------
        bm25_ranked: List[Tuple[str, float]] = []
        if self._bm25.is_built:
            bm25_ranked = self._bm25.search(query, top_k=20)

        bm25_rank: Dict[str, int] = {webid: rank for rank, (webid, _) in enumerate(bm25_ranked)}

        # --- Layer 3: vector similarity search ----------------------------
        vec_hits = self._vdb.search(query, n_results=20)
        vec_rank: Dict[str, int] = {h["webid"]: rank for rank, h in enumerate(vec_hits)}
        vec_meta: Dict[str, Dict] = {h["webid"]: h for h in vec_hits}

        # --- RRF fusion ---------------------------------------------------
        all_webids: set[str] = (
            {w for w, _ in bm25_ranked}
            | {h["webid"] for h in vec_hits}
            | set(alias_hits)
        )

        scores: Dict[str, float] = {}
        for webid in all_webids:
            rrf = 0.0
            if webid in bm25_rank:
                rrf += 1.0 / (RRF_K + bm25_rank[webid] + 1)
            if webid in vec_rank:
                rrf += 1.0 / (RRF_K + vec_rank[webid] + 1)
            rrf += alias_hits.get(webid, 0.0)
            scores[webid] = rrf

        ranked = sorted(scores.items(), key=lambda x: -x[1])[:top_k]

        results: List[ElementMatch] = []
        for webid, score in ranked:
            # Get metadata from graph (authoritative) or vector DB fallback
            node = self._graph.get_node(webid)
            if node:
                results.append(ElementMatch(
                    webid=webid,
                    name=node.get("name", ""),
                    path=node.get("path", ""),
                    template=node.get("template", ""),
                    score=score,
                    match_layer=("alias" if webid in alias_hits else
                                 "bm25+vector" if (webid in bm25_rank and webid in vec_rank) else
                                 "bm25" if webid in bm25_rank else "vector"),
                ))
            elif webid in vec_meta:
                m = vec_meta[webid]
                results.append(ElementMatch(
                    webid=webid,
                    name=m.get("name", ""),
                    path=m.get("path", ""),
                    template=m.get("template", ""),
                    score=score,
                    match_layer="vector",
                ))

        return results

    # ------------------------------------------------------------------ #
    # Attribute resolution
    # ------------------------------------------------------------------ #

    def resolve_attribute(
        self,
        element_webid: str,
        metric_hint: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Within a resolved element, find the attribute best matching
        the metric mentioned in the query.

        Uses synonym expansion: "temperature" → checks for temp, TI, TT, …
        """
        # Try direct lookup via knowledge graph
        attr = self._graph.find_attribute_webid(
            element_webid,
            metric_hint,
            measurement_type=get_measurement_type(metric_hint),
        )
        if attr:
            return attr

        # Fallback: expand metric to aliases and search attribute names
        aliases = get_aliases(metric_hint)
        attrs = self._graph.get_element_attributes(element_webid)
        for alias in aliases:
            alias_lower = alias.lower()
            for a in attrs:
                if alias_lower in a.get("Name", "").lower():
                    return a
        return None

    # ------------------------------------------------------------------ #
    # Full resolution
    # ------------------------------------------------------------------ #

    def resolve(
        self,
        query: str,
        metric_hint: Optional[str] = None,
        top_k: int = 5,
    ) -> Optional[ResolutionResult]:
        """
        Full resolution: element + attribute.

        metric_hint: the measurement type or parameter being queried
                     (e.g. "temperature", "pressure", "vibration").
                     If None, attribute resolution is skipped.

        Returns None if no candidates found.
        """
        elements = self.resolve_elements(query, top_k=top_k)
        if not elements:
            return None

        best = elements[0]
        attr: Optional[Dict[str, Any]] = None

        if metric_hint:
            attr = self.resolve_attribute(best.webid, metric_hint)

        return ResolutionResult(element=best, attribute=attr)

    def resolve_all(
        self,
        query: str,
        metric_hint: Optional[str] = None,
        top_k: int = 5,
    ) -> List[ResolutionResult]:
        """Like resolve() but returns all candidates."""
        elements = self.resolve_elements(query, top_k=top_k)
        results: List[ResolutionResult] = []
        for elem in elements:
            attr: Optional[Dict[str, Any]] = None
            if metric_hint:
                attr = self.resolve_attribute(elem.webid, metric_hint)
            results.append(ResolutionResult(element=elem, attribute=attr))
        return results


# --------------------------------------------------------------------------- #
# Metric extraction from natural language query
# --------------------------------------------------------------------------- #

# Simple keyword-based metric detector.  Covers the most common PI query
# patterns without requiring an LLM call.
_METRIC_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b(temp|temperature|thermal|heat|hot|cold)\b", re.I), "temperature"),
    (re.compile(r"\b(press|pressure|psi|bar|barg|bara|kpa)\b", re.I), "pressure"),
    (re.compile(r"\b(flow|flowrate|flow rate|mmscfd|m3/h|gpm)\b", re.I), "flow"),
    (re.compile(r"\b(level|lvl|liq|liquid level)\b", re.I), "level"),
    (re.compile(r"\b(vibrat|vibr|vib|mm/s)\b", re.I), "vibration"),
    (re.compile(r"\b(speed|rpm|rot)\b", re.I), "speed"),
    (re.compile(r"\b(power|kw|mw|watt)\b", re.I), "power"),
    (re.compile(r"\b(current|amp|amps)\b", re.I), "current"),
    (re.compile(r"\b(health|condition|reliab)\b", re.I), "health"),
    (re.compile(r"\b(status|state|running|stopped|trip|alarm)\b", re.I), "status"),
    (re.compile(r"\b(produc|output|throughput|mmscfd)\b", re.I), "production"),
    (re.compile(r"\b(efficien|eff)\b", re.I), "efficiency"),
]


def extract_metric(query: str) -> Optional[str]:
    """
    Detect the primary metric being queried from a natural language string.
    Returns canonical metric name or None.
    """
    for pattern, metric in _METRIC_PATTERNS:
        if pattern.search(query):
            return metric
    return None


# --------------------------------------------------------------------------- #
# Module-level singleton
# --------------------------------------------------------------------------- #

_resolver: Optional[HybridResolver] = None


def get_resolver() -> HybridResolver:
    global _resolver
    if _resolver is None:
        from bm25_index import get_bm25_index
        from knowledge_graph import get_graph
        from vector_db import get_vector_db
        _resolver = HybridResolver(
            bm25=get_bm25_index(),
            vector_db=get_vector_db(),
            graph=get_graph(),
        )
    return _resolver

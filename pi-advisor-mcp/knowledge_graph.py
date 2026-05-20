"""
NetworkX-based AF hierarchy knowledge graph.

Architecture
------------
  - Nodes  : AF elements only (node-id = WebId string)
  - Edges  : directed parent → child (PARENT_OF relationship)
  - Node attributes stored inline:
      name, path, template, description, depth, is_leaf,
      attributes (list of dicts), measurement_types (set)

Build once at startup from pre-fetched element + attribute data,
persist to disk as pickle for fast restarts.  Rebuilds are coordinated
by the indexing pipeline.

Graph queries are O(V+E) at worst; for typical AF hierarchies (500-2000
nodes) they complete in < 1 ms.
"""

from __future__ import annotations

import logging
import os
import pickle
import time
from typing import Any, Dict, Iterator, List, Optional, Set

import networkx as nx

from config import config
from synonyms import get_measurement_type

logger = logging.getLogger(__name__)

_PICKLE_FILE = "af_graph.pkl"


class AFKnowledgeGraph:
    """
    Directed graph of the PI AF element hierarchy.

    Thread-safety: all public methods are read-only after build; the graph
    object itself is not modified concurrently.  The ``build`` method is
    called from a single asyncio task inside the indexing pipeline.
    """

    def __init__(self) -> None:
        self._g: nx.DiGraph = nx.DiGraph()
        self._built_at: Optional[float] = None
        self._element_count: int = 0
        self._webid_index: Dict[str, str] = {}   # name_lower → webid (first match)
        self._path_index: Dict[str, str] = {}    # path_lower → webid

    # ------------------------------------------------------------------ #
    # Build / persist / load
    # ------------------------------------------------------------------ #

    def build(
        self,
        elements: List[Dict[str, Any]],
        attributes_map: Dict[str, List[Dict[str, Any]]],
    ) -> None:
        """
        Construct the graph from pre-fetched element list and attribute map.

        elements: list of dicts with keys WebId, Name, Path, Description,
                  TemplateName, HasChildren
        attributes_map: {element_webid: [attr_dicts]}
        """
        t0 = time.monotonic()
        g = nx.DiGraph()

        # First pass: add all nodes
        for elem in elements:
            webid = elem.get("WebId", "")
            if not webid:
                continue
            path: str = elem.get("Path", "") or ""
            attrs_list = attributes_map.get(webid, [])
            m_types = {get_measurement_type(a.get("Name", "")) for a in attrs_list}
            m_types.discard("other")

            depth = path.count("\\") if path else 0

            g.add_node(
                webid,
                name=elem.get("Name", ""),
                path=path,
                template=elem.get("TemplateName", ""),
                description=elem.get("Description", ""),
                has_children=bool(elem.get("HasChildren", False)),
                is_leaf=not bool(elem.get("HasChildren", False)),
                depth=depth,
                attributes=attrs_list,
                measurement_types=m_types,
            )

        # Second pass: reconstruct parent-child edges from paths
        # Path format: \\AFServer\Database\Level1\Level2\...\ElementName
        path_to_webid: Dict[str, str] = {}
        for webid, data in g.nodes(data=True):
            if data["path"]:
                path_to_webid[data["path"].lower()] = webid

        for webid, data in g.nodes(data=True):
            path = data["path"]
            if not path:
                continue
            parent_path = path.rsplit("\\", 1)[0]
            parent_webid = path_to_webid.get(parent_path.lower())
            if parent_webid and parent_webid != webid:
                g.add_edge(parent_webid, webid)

        self._g = g
        self._element_count = g.number_of_nodes()
        self._built_at = time.monotonic()

        # Build name + path indexes for fast lookup
        self._webid_index = {}
        self._path_index = {}
        for webid, data in g.nodes(data=True):
            name_lower = data["name"].lower()
            if name_lower not in self._webid_index:
                self._webid_index[name_lower] = webid
            if data["path"]:
                self._path_index[data["path"].lower()] = webid

        elapsed = round((time.monotonic() - t0) * 1000)
        logger.info(
            "Knowledge graph built: %d nodes, %d edges in %d ms",
            g.number_of_nodes(), g.number_of_edges(), elapsed,
        )

    def save(self) -> bool:
        """Persist graph to disk."""
        persist_dir = config.graph.persist_path
        os.makedirs(persist_dir, exist_ok=True)
        path = os.path.join(persist_dir, _PICKLE_FILE)
        try:
            with open(path, "wb") as f:
                pickle.dump(
                    {
                        "graph": self._g,
                        "built_at": self._built_at,
                        "webid_index": self._webid_index,
                        "path_index": self._path_index,
                    },
                    f,
                    protocol=pickle.HIGHEST_PROTOCOL,
                )
            logger.info("Knowledge graph saved to %s", path)
            return True
        except Exception as exc:
            logger.error("Failed to save knowledge graph: %s", exc)
            return False

    def load(self) -> bool:
        """Load graph from disk.  Returns True if successful."""
        path = os.path.join(config.graph.persist_path, _PICKLE_FILE)
        if not os.path.exists(path):
            return False
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            self._g = data["graph"]
            self._built_at = data.get("built_at")
            self._webid_index = data.get("webid_index", {})
            self._path_index = data.get("path_index", {})
            self._element_count = self._g.number_of_nodes()
            logger.info("Knowledge graph loaded: %d nodes from %s", self._element_count, path)
            return True
        except Exception as exc:
            logger.warning("Failed to load knowledge graph: %s", exc)
            return False

    @property
    def is_built(self) -> bool:
        return self._element_count > 0

    # ------------------------------------------------------------------ #
    # Lookup helpers
    # ------------------------------------------------------------------ #

    def webid_by_name(self, name: str) -> Optional[str]:
        return self._webid_index.get(name.lower())

    def webid_by_path(self, path: str) -> Optional[str]:
        return self._path_index.get(path.lower())

    def get_node(self, webid: str) -> Optional[Dict[str, Any]]:
        """Return node attribute dict or None."""
        if webid in self._g:
            return dict(self._g.nodes[webid])
        return None

    def all_webids(self) -> List[str]:
        return list(self._g.nodes())

    def all_elements(self) -> Iterator[tuple[str, Dict[str, Any]]]:
        """Iterate (webid, data) for all element nodes."""
        yield from self._g.nodes(data=True)

    # ------------------------------------------------------------------ #
    # Traversal queries
    # ------------------------------------------------------------------ #

    def get_children(self, webid: str) -> List[Dict[str, Any]]:
        """Direct child elements."""
        return [
            {"webid": c, **self._g.nodes[c]}
            for c in self._g.successors(webid)
            if c in self._g
        ]

    def get_parent(self, webid: str) -> Optional[Dict[str, Any]]:
        preds = list(self._g.predecessors(webid))
        if not preds:
            return None
        p = preds[0]
        return {"webid": p, **self._g.nodes[p]}

    def get_ancestors(self, webid: str, max_depth: int = 10) -> List[Dict[str, Any]]:
        """All ancestors from immediate parent up to root, shallowest first."""
        result: List[Dict[str, Any]] = []
        current = webid
        seen: Set[str] = {webid}
        for _ in range(max_depth):
            preds = [p for p in self._g.predecessors(current) if p not in seen]
            if not preds:
                break
            p = preds[0]
            seen.add(p)
            result.append({"webid": p, **self._g.nodes[p]})
            current = p
        return result

    def get_descendants(
        self,
        webid: str,
        max_depth: int = 5,
        template_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        All descendant elements (BFS), optionally filtered by template name.
        """
        result: List[Dict[str, Any]] = []
        queue: list[tuple[str, int]] = [(webid, 0)]
        visited: Set[str] = {webid}

        while queue:
            node, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            for child in self._g.successors(node):
                if child in visited:
                    continue
                visited.add(child)
                data = self._g.nodes[child]
                if template_filter is None or template_filter.lower() in data.get("template", "").lower():
                    result.append({"webid": child, **data})
                queue.append((child, depth + 1))

        return result

    def get_siblings(self, webid: str) -> List[Dict[str, Any]]:
        """Elements sharing the same parent as webid, excluding webid itself."""
        preds = list(self._g.predecessors(webid))
        if not preds:
            return []
        parent = preds[0]
        return [
            {"webid": s, **self._g.nodes[s]}
            for s in self._g.successors(parent)
            if s != webid and s in self._g
        ]

    def get_root_elements(self) -> List[Dict[str, Any]]:
        """Elements with no parent (top-level under AF database)."""
        return [
            {"webid": n, **data}
            for n, data in self._g.nodes(data=True)
            if self._g.in_degree(n) == 0
        ]

    # ------------------------------------------------------------------ #
    # Attribute-aware queries
    # ------------------------------------------------------------------ #

    def get_element_attributes(self, webid: str) -> List[Dict[str, Any]]:
        node = self.get_node(webid)
        if not node:
            return []
        return node.get("attributes", [])

    def find_attribute_webid(
        self,
        element_webid: str,
        attr_name_hint: str,
        measurement_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find the best-matching attribute within an element.

        Matching priority:
        1. Exact name match (case-insensitive)
        2. Name contains hint
        3. Measurement type match
        Returns the attribute dict (including WebId) or None.
        """
        attrs = self.get_element_attributes(element_webid)
        if not attrs:
            return None

        hint_lower = attr_name_hint.lower()

        # Exact match
        for attr in attrs:
            if attr.get("Name", "").lower() == hint_lower:
                return attr

        # Partial name match
        candidates = [a for a in attrs if hint_lower in a.get("Name", "").lower()]
        if candidates:
            return candidates[0]

        # Measurement type match
        if measurement_type:
            mt_lower = measurement_type.lower()
            for attr in attrs:
                if get_measurement_type(attr.get("Name", "")) == mt_lower:
                    return attr

        return None

    def find_elements_by_measurement(
        self,
        measurement_type: str,
        subtree_webid: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find all elements that have at least one attribute of the given
        measurement type.  Optionally scoped to a subtree.
        """
        scope: set[str]
        if subtree_webid:
            scope = {d["webid"] for d in self.get_descendants(subtree_webid)}
            scope.add(subtree_webid)
        else:
            scope = set(self._g.nodes())

        mt = measurement_type.lower()
        result: List[Dict[str, Any]] = []
        for webid in scope:
            data = self._g.nodes.get(webid, {})
            if mt in {m.lower() for m in data.get("measurement_types", set())}:
                result.append({"webid": webid, **data})
        return result

    # ------------------------------------------------------------------ #
    # Higher-level analytical queries
    # ------------------------------------------------------------------ #

    def get_impact_analysis(self, webid: str) -> Dict[str, Any]:
        """
        Return the set of elements likely affected if this element is
        taken offline:
          - All descendants (feed this element's output)
          - Siblings (same process train / section may be interdependent)
        """
        node = self.get_node(webid)
        if not node:
            return {"error": f"Element {webid} not found in graph"}

        descendants = self.get_descendants(webid, max_depth=config.graph.max_depth)
        siblings = self.get_siblings(webid)
        parent = self.get_parent(webid)

        return {
            "element": {"webid": webid, **node},
            "parent": parent,
            "direct_downstream_count": len(descendants),
            "sibling_count": len(siblings),
            "affected_descendants": descendants,
            "peer_elements": siblings,
            "summary": (
                f"Shutting down '{node['name']}' directly affects "
                f"{len(descendants)} downstream element(s) and "
                f"{len(siblings)} peer element(s) in the same section."
            ),
        }

    def get_investigation_context(self, webid: str) -> Dict[str, Any]:
        """
        Gather context for root-cause analysis of an anomaly at webid:
          - The element itself + attributes
          - Parent chain (process context)
          - Siblings (comparison baseline)
          - Children (sub-component detail)
        """
        node = self.get_node(webid)
        if not node:
            return {"error": f"Element {webid} not found in graph"}

        return {
            "element": {"webid": webid, **node},
            "attributes": self.get_element_attributes(webid),
            "ancestors": self.get_ancestors(webid),
            "siblings": self.get_siblings(webid),
            "children": self.get_children(webid),
            "measurement_types": list(node.get("measurement_types", set())),
        }

    def compare_siblings(self, webid: str) -> Dict[str, Any]:
        """
        Return sibling elements alongside the target element so the caller
        can fetch their values and produce a comparative view.
        """
        node = self.get_node(webid)
        if not node:
            return {"error": f"Element {webid} not found in graph"}
        siblings = self.get_siblings(webid)
        return {
            "reference": {"webid": webid, **node},
            "peers": siblings,
            "total": len(siblings) + 1,
        }

    def find_instruments_in_subtree(
        self,
        webid: str,
        instrument_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find all leaf-node elements (instruments / sensors) within a subtree,
        optionally filtered by template name keywords.
        """
        descendants = self.get_descendants(webid, max_depth=config.graph.max_depth)
        instruments = [d for d in descendants if d.get("is_leaf")]
        if instrument_types:
            filters_lower = [t.lower() for t in instrument_types]
            instruments = [
                d for d in instruments
                if any(f in d.get("template", "").lower() for f in filters_lower)
            ]
        return instruments

    # ------------------------------------------------------------------ #
    # Statistics
    # ------------------------------------------------------------------ #

    def get_stats(self) -> Dict[str, Any]:
        if not self.is_built:
            return {"built": False}
        built_age_s = round(time.monotonic() - self._built_at) if self._built_at else None
        leaf_count = sum(1 for _, d in self._g.nodes(data=True) if d.get("is_leaf"))
        template_counts: Dict[str, int] = {}
        for _, data in self._g.nodes(data=True):
            t = data.get("template", "") or "Unknown"
            template_counts[t] = template_counts.get(t, 0) + 1

        return {
            "built": True,
            "node_count": self._g.number_of_nodes(),
            "edge_count": self._g.number_of_edges(),
            "leaf_nodes": leaf_count,
            "root_nodes": len(self.get_root_elements()),
            "built_age_seconds": built_age_s,
            "template_distribution": dict(
                sorted(template_counts.items(), key=lambda x: -x[1])[:10]
            ),
        }


# Module-level singleton
_graph: Optional[AFKnowledgeGraph] = None


def get_graph() -> AFKnowledgeGraph:
    global _graph
    if _graph is None:
        _graph = AFKnowledgeGraph()
    return _graph

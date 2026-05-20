"""
BM25 keyword search index over AF element documents.

Provides fast lexical matching for PI tag names, abbreviations, and ISA
codes (e.g. "GS-01", "K-101", "TI-101") that vector similarity alone
may rank poorly due to lack of training on industrial naming conventions.

Tokenisation preserves hyphenated identifiers both as a whole token and
as split parts (K-101 → ["k", "101", "k-101"]) to maximise recall.
"""

from __future__ import annotations

import logging
import os
import pickle
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from rank_bm25 import BM25Okapi

from config import config
from synonyms import expand_query

logger = logging.getLogger(__name__)

_PICKLE_FILE = "bm25_index.pkl"


def _tokenise(text: str) -> List[str]:
    """
    Tokenise text for BM25.

    Rules:
    - Lowercase everything
    - Split on whitespace, slash, comma, semicolon, parentheses
    - For hyphenated tokens keep both whole and parts (K-101 → k-101, k, 101)
    - For underscore-joined tokens keep both whole and parts
    - No stopword removal (PI abbreviations are meaningful)
    """
    text = text.lower()
    raw_tokens = re.split(r"[\s/,;()\[\]]+", text)
    tokens: List[str] = []
    for tok in raw_tokens:
        if not tok:
            continue
        tokens.append(tok)
        if "-" in tok:
            parts = tok.split("-")
            tokens.extend(p for p in parts if p)
        if "_" in tok:
            parts = tok.split("_")
            tokens.extend(p for p in parts if p)
    return tokens


def _build_document(element: Dict[str, Any]) -> str:
    """
    Flatten an element dict into a BM25-indexable string.

    Includes: name, description, path components, template, attribute names.
    Path components are expanded individually to improve partial-path matching.
    """
    parts: List[str] = []

    name = element.get("name") or element.get("Name", "")
    parts.append(name)
    # Repeat name to boost its weight in BM25
    parts.append(name)

    desc = element.get("description") or element.get("Description", "")
    if desc:
        parts.append(desc)

    path = element.get("path") or element.get("Path", "")
    if path:
        # Each path component individually
        parts.extend(c for c in path.split("\\") if c)

    template = element.get("template") or element.get("TemplateName", "")
    if template:
        parts.append(template)

    # Attribute names
    for attr in element.get("attributes", []):
        attr_name = attr.get("Name", "")
        if attr_name:
            parts.append(attr_name)
        units = attr.get("DefaultUnitsName", "")
        if units:
            parts.append(units)

    return " ".join(parts)


class BM25Index:
    """
    Wraps rank_bm25.BM25Okapi with document metadata, persistence,
    and synonym-expanded querying.
    """

    def __init__(self) -> None:
        self._bm25: Optional[BM25Okapi] = None
        self._webids: List[str] = []        # positional index → webid
        self._built_at: Optional[float] = None

    @property
    def is_built(self) -> bool:
        return self._bm25 is not None

    def build(self, elements: List[Dict[str, Any]]) -> None:
        """
        Build index from a list of element dicts.
        Each dict must have at least 'webid'/'WebId' and 'name'/'Name'.
        Attributes should be pre-merged under key 'attributes'.
        """
        t0 = time.monotonic()
        self._webids = []
        tokenised_docs: List[List[str]] = []

        for elem in elements:
            webid = elem.get("webid") or elem.get("WebId", "")
            if not webid:
                continue
            self._webids.append(webid)
            doc = _build_document(elem)
            tokenised_docs.append(_tokenise(doc))

        self._bm25 = BM25Okapi(
            tokenised_docs,
            k1=config.bm25.k1,
            b=config.bm25.b,
        )
        self._built_at = time.monotonic()
        elapsed = round((time.monotonic() - t0) * 1000)
        logger.info("BM25 index built: %d documents in %d ms", len(self._webids), elapsed)

    def search(self, query: str, top_k: int = 20) -> List[Tuple[str, float]]:
        """
        Return [(webid, score), ...] sorted descending by BM25 score.
        Applies domain synonym expansion before tokenisation.
        """
        if not self.is_built:
            return []

        expanded = expand_query(query)
        tokens = _tokenise(expanded)
        if not tokens:
            return []

        scores = self._bm25.get_scores(tokens)
        ranked = sorted(
            ((self._webids[i], float(scores[i])) for i in range(len(self._webids)) if scores[i] > 0),
            key=lambda x: -x[1],
        )
        return ranked[:top_k]

    def save(self) -> bool:
        persist_dir = config.bm25.persist_path
        os.makedirs(persist_dir, exist_ok=True)
        path = os.path.join(persist_dir, _PICKLE_FILE)
        try:
            with open(path, "wb") as f:
                pickle.dump(
                    {"bm25": self._bm25, "webids": self._webids, "built_at": self._built_at},
                    f,
                    protocol=pickle.HIGHEST_PROTOCOL,
                )
            logger.info("BM25 index saved to %s", path)
            return True
        except Exception as exc:
            logger.error("Failed to save BM25 index: %s", exc)
            return False

    def load(self) -> bool:
        path = os.path.join(config.bm25.persist_path, _PICKLE_FILE)
        if not os.path.exists(path):
            return False
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            self._bm25 = data["bm25"]
            self._webids = data["webids"]
            self._built_at = data.get("built_at")
            logger.info("BM25 index loaded: %d documents from %s", len(self._webids), path)
            return True
        except Exception as exc:
            logger.warning("Failed to load BM25 index: %s", exc)
            return False

    def get_stats(self) -> Dict[str, Any]:
        return {
            "built": self.is_built,
            "document_count": len(self._webids),
            "built_age_seconds": (
                round(time.monotonic() - self._built_at) if self._built_at else None
            ),
        }


# Module-level singleton
_index: Optional[BM25Index] = None


def get_bm25_index() -> BM25Index:
    global _index
    if _index is None:
        _index = BM25Index()
    return _index

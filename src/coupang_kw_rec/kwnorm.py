"""Dependency-free keyword normalization shared by other tools.

코어 repo와 동기화 필요: coupang-kw/src/kwnorm.py
"""

from __future__ import annotations

import re
import unicodedata


KWNORM_CONTRACT_VERSION = "1.0.0"
_SPACE_RE = re.compile(r"\s+")
_EDGE_PUNCTUATION = ",.'\"`~!@#$%^&()[]{}<>?;:|\\/"


def normalize_keyword(s: str) -> str:
    """Return a stable comparison form while preserving dimensions such as 120x120."""
    if s is None:
        return ""
    value = unicodedata.normalize("NFKC", str(s)).casefold().strip()
    value = value.strip(_EDGE_PUNCTUATION)
    return _SPACE_RE.sub(" ", value).strip()


def tokenize(s: str) -> list[str]:
    """Split a normalized keyword on whitespace without external dependencies."""
    normalized = normalize_keyword(s)
    return normalized.split(" ") if normalized else []

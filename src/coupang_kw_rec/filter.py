"""Ordered keyword safety and relevance filters."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import math
import re
from typing import Any, Iterable

from .kwnorm import normalize_keyword
from .source import InputData


@dataclass
class FilterResult:
    candidates: list[dict[str, Any]] = field(default_factory=list)
    held: list[dict[str, Any]] = field(default_factory=list)
    reverse_excludes: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    stage_counts: Counter = field(default_factory=Counter)


def _contains_term(keyword: str, term: str, english_boundary: bool = False) -> bool:
    normalized_keyword = normalize_keyword(keyword)
    normalized_term = normalize_keyword(term)
    if not normalized_term:
        return False
    if english_boundary and normalized_term.isascii():
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])", normalized_keyword))
    return normalized_term in normalized_keyword


def detect_own_brand(keyword: str, config: dict[str, Any]) -> str:
    matches: list[str] = []
    boundary = config["brands"].get("english_word_boundary", True)
    for canonical, variants in config["brands"]["own"].items():
        terms = [canonical, *variants]
        if any(_contains_term(keyword, term, boundary) for term in terms):
            matches.append(canonical)
    return "MULTI" if len(matches) > 1 else (matches[0] if matches else "NONE")


def _first_match(keyword: str, terms: Iterable[str], english_boundary: bool = True) -> str | None:
    for term in terms:
        if _contains_term(keyword, term, english_boundary):
            return term
    return None


def _clean_keyword(keyword: Any, pattern: str) -> str:
    value = re.sub(pattern, " ", str(keyword or ""))
    return re.sub(r"\s+", " ", value).strip()


def _keywords(rows: list[dict[str, Any]]) -> set[str]:
    return {normalize_keyword(row.get("keyword")) for row in rows if normalize_keyword(row.get("keyword"))}


def apply_filters(
    rows: list[dict[str, Any]],
    source_data: InputData,
    exclude_keywords: list[str],
    config: dict[str, Any],
) -> FilterResult:
    rules = config["filters"]
    result = FilterResult()
    existing = _keywords(source_data.keyword_rows)
    converting = _keywords(source_data.converting_rows)
    exclusions = [normalize_keyword(value) for value in exclude_keywords if normalize_keyword(value)]

    for original in rows:
        row = dict(original)
        row["keyword"] = _clean_keyword(row.get("keyword"), rules["special_character_pattern"])
        key = normalize_keyword(row["keyword"])
        row["brand"] = detect_own_brand(row["keyword"], config)
        row["already_converting"] = key in converting
        row.setdefault("note", "")

        if key in existing and key not in converting:
            _reject(result, row, "1_기존키워드")
            continue
        if any(excluded == key or excluded in key for excluded in exclusions):
            _reject(result, row, "2_제외키워드")
            continue

        competitor = _first_match(row["keyword"], rules["competitor_brands"])
        ambiguous = _first_match(row["keyword"], rules["ambiguous_brand_terms"])
        if competitor and row["brand"] == "NONE":
            _reject(result, row, "3_타사브랜드", f"타사 브랜드: {competitor}")
            continue
        if ambiguous and row["brand"] == "NONE":
            _hold(result, row, "3_브랜드의심", f"브랜드 의심: {ambiguous}")
            continue

        category_terms = rules["category_must_include_any"]
        if category_terms and not any(_contains_term(row["keyword"], term) for term in category_terms):
            _hold(result, row, "4_카테고리관련성", "필수 카테고리 단어 없음")
            continue

        forbidden = _first_match(row["keyword"], rules["forbidden_terms"], False)
        if forbidden:
            _reject(result, row, "5_금칙어", f"금칙어: {forbidden}")
            continue

        length = len(row["keyword"].replace(" ", ""))
        if length < rules["keyword_min_length"] or length > rules["keyword_max_length"]:
            _reject(result, row, "6_길이")
            continue

        absent = _first_match(row["keyword"], rules["product_absent_terms"], False)
        if absent:
            row["reason"] = f"미보유 기능: {absent}"
            result.reverse_excludes.append(row)
            result.stage_counts["상품미보유기능"] += 1
            continue

        volume = row.get("search_volume")
        below_volume = _is_number(volume) and float(volume) < rules["min_search_volume"]
        if (not _is_number(volume) or below_volume) and row["brand"] == "NONE":
            _reject(result, row, "7_최소검색량")
            continue

        result.candidates.append(row)
    result.stage_counts["통과"] = len(result.candidates)
    return result


def _is_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _reject(result: FilterResult, row: dict[str, Any], stage: str, reason: str = "") -> None:
    row["reason"] = reason or stage
    result.rejected.append(row)
    result.stage_counts[stage] += 1


def _hold(result: FilterResult, row: dict[str, Any], stage: str, reason: str) -> None:
    row["reason"] = reason
    result.held.append(row)
    result.stage_counts[stage] += 1

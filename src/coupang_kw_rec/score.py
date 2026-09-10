"""Keyword scoring, grading, and brand-preserving limiting."""

from __future__ import annotations

import math
from typing import Any

from .kwnorm import normalize_keyword, tokenize


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    low, high = min(values), max(values)
    if high == low:
        return [1.0 if high > 0 else 0.0 for _ in values]
    return [(value - low) / (high - low) for value in values]


def _relevance(keyword: str, seeds: list[str]) -> float:
    candidate = set(tokenize(keyword))
    if not candidate:
        return 0.0
    best = 0.0
    normalized_keyword = normalize_keyword(keyword).replace(" ", "")
    for seed in seeds:
        seed_tokens = set(tokenize(seed))
        if not seed_tokens:
            continue
        union = candidate | seed_tokens
        jaccard = len(candidate & seed_tokens) / len(union)
        seed_compact = normalize_keyword(seed).replace(" ", "")
        if seed_compact in normalized_keyword or normalized_keyword in seed_compact:
            jaccard = max(jaccard, 1.0)
        best = max(best, jaccard)
    return best


def score_keywords(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    if not rows:
        return []
    rules = config["scoring"]
    volumes = [math.log1p(max(0.0, _number(row.get("search_volume")))) for row in rows]
    seed_scores = [math.log1p(max(0.0, _number(row.get("seed_score")))) for row in rows]
    norm_volume = _normalize(volumes)
    norm_seed = _normalize(seed_scores)
    comp_map = {normalize_keyword(key): value for key, value in rules["competition_scores"].items()}
    scored: list[dict[str, Any]] = []
    for index, original in enumerate(rows):
        row = dict(original)
        relevance = _relevance(row["keyword"], row.get("seed_keywords", []))
        mobile_ratio = _number(row.get("mobile_ratio"))
        comp_score = comp_map.get(normalize_keyword(row.get("comp_idx")), rules["unknown_competition_score"])
        score = (
            rules["w_volume"] * norm_volume[index]
            + rules["w_mobile"] * mobile_ratio
            + rules["w_seed_perf"] * norm_seed[index]
            + rules["w_relevance"] * relevance
            - rules["w_comp"] * comp_score
            + rules["seed_count_bonus"] * _number(row.get("seed_count"))
        )
        row["relevance"] = round(relevance, 6)
        row["score"] = round(score, 6)
        row["seed_roas"] = _number(row.get("seed_roas"), math.nan)
        scored.append(row)
    scored.sort(key=lambda row: (-row["score"], -_number(row.get("search_volume")), normalize_keyword(row["keyword"])))
    count = len(scored)
    high_volume_threshold = sorted((_number(row.get("search_volume")) for row in scored), reverse=True)[
        min(count - 1, max(0, math.ceil(count * rules["high_volume_top_fraction"]) - 1))
    ]
    for index, row in enumerate(scored, start=1):
        fraction = index / count
        if row.get("brand") not in (None, "", "NONE"):
            grade = rules["brand_grade"]
        elif fraction <= rules["grade_a_top_fraction"] and _number(row.get("search_volume")) >= high_volume_threshold:
            grade = rules["grade_a"]
        elif fraction <= rules["grade_b_top_fraction"]:
            grade = rules["grade_b"]
        else:
            grade = rules["grade_c"]
        row["rec_grade"] = grade
        row["action_ko"] = rules["actions"][grade]
    return scored


def apply_limit(rows: list[dict[str, Any]], requested_limit: int, config: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    hard_max = config["output"]["limit_max"]
    limit = max(1, min(int(requested_limit), hard_max))
    brand_grade = config["scoring"]["brand_grade"]
    brands = [row for row in rows if row.get("rec_grade") == brand_grade]
    others = [row for row in rows if row.get("rec_grade") != brand_grade]
    kept = brands[:limit]
    kept.extend(others[: max(0, limit - len(kept))])
    kept.sort(key=lambda row: (-row["score"], -_number(row.get("search_volume")), normalize_keyword(row["keyword"])))
    for rank, row in enumerate(kept, start=1):
        row["rank"] = rank
    return kept, max(0, len(rows) - len(kept))

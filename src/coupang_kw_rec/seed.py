"""Deterministic seed selection with reasons."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from .kwnorm import normalize_keyword
from .source import InputData


@dataclass
class SeedChoice:
    keyword: str
    reason: str
    seed_score: float
    seed_roas: float = math.nan


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def select_seeds(data: InputData, config: dict[str, Any]) -> list[SeedChoice]:
    rules = config["seed_selection"]
    selected: dict[str, SeedChoice] = {}

    def add(keyword: Any, reason: str, score: float, seed_roas: float = math.nan) -> None:
        key = normalize_keyword(keyword)
        if not key:
            return
        candidate = SeedChoice(str(keyword).strip(), reason, score, seed_roas)
        current = selected.get(key)
        if current is None or candidate.seed_score > current.seed_score:
            selected[key] = candidate

    for keyword in data.direct_seeds:
        add(keyword, rules["reason_labels"]["direct"], rules["direct_seed_score"])

    performance = [row for row in data.keyword_rows if _number(row.get("orders")) > 0]
    performance.sort(key=lambda row: _number(row.get("revenue")), reverse=True)
    for row in performance[:rules["performance_count"]]:
        add(row.get("keyword"), rules["reason_labels"]["performance"], _number(row.get("revenue")), _number(row.get("ROAS"), math.nan))

    volume = sorted(
        data.keyword_rows,
        key=lambda row: (_number(row.get("impressions")), _number(row.get("CTR"))),
        reverse=True,
    )
    for row in volume[:rules["volume_count"]]:
        add(row.get("keyword"), rules["reason_labels"]["volume"], _number(row.get("impressions")), _number(row.get("ROAS"), math.nan))

    for canonical, variants in config["brands"]["own"].items():
        for keyword in [canonical, *variants]:
            add(keyword, rules["reason_labels"]["brand"], rules["brand_seed_score"])

    tokens = [row for row in data.token_rows if _number(row.get("CVR")) >= rules["token_min_cvr"]]
    tokens.sort(key=lambda row: _number(row.get("clicks")), reverse=True)
    for row in tokens[:rules["token_count"]]:
        add(row.get("token"), rules["reason_labels"]["token"], _number(row.get("clicks")), _number(row.get("ROAS"), math.nan))

    brand_reason = rules["reason_labels"]["brand"]
    brands = [choice for choice in selected.values() if choice.reason == brand_reason]
    others = [choice for choice in selected.values() if choice.reason != brand_reason]
    brands.sort(key=lambda item: normalize_keyword(item.keyword))
    others.sort(key=lambda item: (-item.seed_score, normalize_keyword(item.keyword)))
    return (brands + others)[:rules["max_seeds"]]

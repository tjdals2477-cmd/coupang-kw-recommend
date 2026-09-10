"""End-to-end orchestration shared by the CLI and Streamlit app."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .filter import FilterResult, apply_filters
from .naver_api import CollectionResult, Credentials, NaverKeywordClient
from .score import apply_limit, score_keywords
from .seed import SeedChoice, select_seeds
from .source import InputData


@dataclass
class PipelineResult:
    seeds: list[SeedChoice]
    collection: CollectionResult
    filters: FilterResult
    scored_all: list[dict[str, Any]]
    recommendations: list[dict[str, Any]]
    trimmed_count: int
    warnings: list[str]


def run_pipeline(
    source_data: InputData,
    exclude_keywords: list[str],
    config: dict[str, Any],
    credentials: Credentials,
    limit: int,
    offline: bool = False,
    cache_dir: str | Path | None = None,
    client: NaverKeywordClient | None = None,
) -> PipelineResult:
    seeds = select_seeds(source_data, config)
    api_client = client or NaverKeywordClient(credentials, config["naver_api"], cache_dir=cache_dir)
    collection = api_client.collect(seeds, offline=offline)
    ctr_scale = config["naver_api"]["ctr_percent_scale"]
    for row in collection.candidates:
        if _is_finite(row.get("naver_avg_ctr")):
            row["naver_avg_ctr"] = float(row["naver_avg_ctr"]) / ctr_scale
    filtered = apply_filters(collection.candidates, source_data, exclude_keywords, config)
    scored = score_keywords(filtered.candidates, config)
    recommendations, trimmed = apply_limit(scored, limit, config)
    warnings = list(source_data.warnings)
    parse_failures = sum(
        1
        for row in collection.candidates
        for field in config["quality"]["numeric_fields"]
        if not _is_finite(row.get(field))
    )
    if parse_failures:
        warnings.append(f"숫자 파싱 실패 또는 결측 {parse_failures}건은 NaN으로 유지했습니다.")
    return PipelineResult(seeds, collection, filtered, scored, recommendations, trimmed, warnings)


def _is_finite(value: Any) -> bool:
    try:
        from math import isfinite
        return isfinite(float(value))
    except (TypeError, ValueError):
        return False

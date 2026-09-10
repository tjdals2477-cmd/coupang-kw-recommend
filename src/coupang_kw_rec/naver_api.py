"""Naver Search Ads keyword tool client with cache and resilient chunk handling."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import time
from typing import Any, Callable, Iterable

from .kwnorm import normalize_keyword
from .seed import SeedChoice


@dataclass(frozen=True)
class Credentials:
    api_key: str
    secret_key: str
    customer_id: str

    @classmethod
    def from_env(cls) -> "Credentials":
        return cls(
            os.getenv("NAVER_AD_API_KEY", "").strip(),
            os.getenv("NAVER_AD_SECRET_KEY", "").strip(),
            os.getenv("NAVER_AD_CUSTOMER_ID", "").strip(),
        )

    @property
    def complete(self) -> bool:
        return bool(self.api_key and self.secret_key and self.customer_id)


@dataclass
class CollectionResult:
    candidates: list[dict[str, Any]] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)
    api_calls: int = 0
    successful_chunks: int = 0
    cache_hits: int = 0
    total_chunks: int = 0


def make_signature(timestamp: str, method: str, uri: str, secret_key: str) -> str:
    message = f"{timestamp}.{method}.{uri}"
    digest = hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def parse_metric(value: Any, low_volume_replacement: float = 5.0) -> float:
    if value is None or isinstance(value, bool):
        return math.nan
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else math.nan
    text = str(value).strip()
    if not text:
        return math.nan
    if text.startswith("<"):
        return float(low_volume_replacement)
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    return float(match.group(0)) if match else math.nan


def _safe_sum(left: float, right: float) -> float:
    if math.isnan(left) and math.isnan(right):
        return math.nan
    return (0.0 if math.isnan(left) else left) + (0.0 if math.isnan(right) else right)


def parse_keyword_row(row: dict[str, Any], low_volume_replacement: float) -> dict[str, Any]:
    pc = parse_metric(row.get("monthlyPcQcCnt"), low_volume_replacement)
    mobile = parse_metric(row.get("monthlyMobileQcCnt"), low_volume_replacement)
    total = _safe_sum(pc, mobile)
    mobile_ratio = mobile / total if not math.isnan(total) and total > 0 and not math.isnan(mobile) else math.nan
    pc_ctr = parse_metric(row.get("monthlyAvePcCtr"), low_volume_replacement)
    mobile_ctr = parse_metric(row.get("monthlyAveMobileCtr"), low_volume_replacement)
    ctr_values = [value for value in (pc_ctr, mobile_ctr) if not math.isnan(value)]
    return {
        "keyword": str(row.get("relKeyword", "")).strip(),
        "pc_qc": pc,
        "mobile_qc": mobile,
        "search_volume": total,
        "mobile_ratio": mobile_ratio,
        "comp_idx": row.get("compIdx"),
        "pl_avg_depth": parse_metric(row.get("plAvgDepth"), low_volume_replacement),
        "naver_avg_ctr": sum(ctr_values) / len(ctr_values) if ctr_values else math.nan,
    }


def _chunks(values: list[SeedChoice], size: int) -> Iterable[list[SeedChoice]]:
    for index in range(0, len(values), size):
        yield values[index:index + size]


def _wire_keyword(value: str) -> str:
    return re.sub(r"\s+", "", value).upper()


def _cache_key(chunk: list[SeedChoice], config: dict[str, Any]) -> str:
    payload = {
        "seeds": [_wire_keyword(choice.keyword) for choice in chunk],
        "showDetail": config["show_detail"],
        "uri": config["uri"],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()


class NaverKeywordClient:
    def __init__(
        self,
        credentials: Credentials,
        config: dict[str, Any],
        cache_dir: str | Path | None = None,
        session: Any | None = None,
        clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.credentials = credentials
        self.config = config
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".coupang-kw-rec" / "cache"
        if session is None:
            import requests
            session = requests.Session()
        self.session = session
        self.clock = clock
        self.sleeper = sleeper

    def _read_cache(self, cache_file: Path) -> dict[str, Any] | None:
        if not cache_file.exists():
            return None
        age = self.clock() - cache_file.stat().st_mtime
        if age > self.config["cache_ttl_days"] * 86400:
            return None
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _write_cache(self, cache_file: Path, payload: dict[str, Any]) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def collect(self, seeds: list[SeedChoice], offline: bool = False) -> CollectionResult:
        result = CollectionResult()
        aggregated: dict[str, dict[str, Any]] = {}
        seed_scores = {normalize_keyword(choice.keyword): choice.seed_score for choice in seeds}
        for chunk_index, chunk in enumerate(_chunks(seeds, self.config["chunk_size"]), start=1):
            result.total_chunks += 1
            key = _cache_key(chunk, self.config)
            cache_file = self.cache_dir / f"{key}.json"
            payload = self._read_cache(cache_file)
            if payload is not None:
                result.cache_hits += 1
                result.successful_chunks += 1
            elif offline:
                result.failures.append({
                    "chunk": chunk_index,
                    "seed_keywords": ", ".join(choice.keyword for choice in chunk),
                    "status": "OFFLINE_CACHE_MISS",
                    "error": "유효한 캐시 없음",
                    "attempts": 0,
                })
                continue
            else:
                if not self.credentials.complete:
                    result.failures.append({
                        "chunk": chunk_index,
                        "seed_keywords": ", ".join(choice.keyword for choice in chunk),
                        "status": "MISSING_CREDENTIALS",
                        "error": "네이버 검색광고 API 자격증명 누락",
                        "attempts": 0,
                    })
                    continue
                if result.api_calls:
                    self.sleeper(self.config["request_interval_seconds"])
                payload = self._request_chunk(chunk, chunk_index, result)
                if payload is None:
                    continue
                result.successful_chunks += 1
                self._write_cache(cache_file, payload)

            chunk_keywords = [choice.keyword for choice in chunk]
            best_choice = max(chunk, key=lambda choice: choice.seed_score, default=SeedChoice("", "", 0.0))
            best_seed_score = best_choice.seed_score
            for raw_row in payload.get("keywordList", []):
                parsed = parse_keyword_row(raw_row, self.config["low_volume_replacement"])
                keyword_key = normalize_keyword(parsed["keyword"])
                if not keyword_key:
                    continue
                current = aggregated.get(keyword_key)
                if current is None:
                    parsed["seed_keywords"] = set(chunk_keywords)
                    parsed["seed_score"] = best_seed_score
                    parsed["seed_roas"] = best_choice.seed_roas
                    aggregated[keyword_key] = parsed
                else:
                    current["seed_keywords"].update(chunk_keywords)
                    current["seed_score"] = max(current["seed_score"], best_seed_score)
                    if best_seed_score >= current["seed_score"]:
                        current["seed_roas"] = best_choice.seed_roas
                    if _numeric_or_negative(parsed["search_volume"]) > _numeric_or_negative(current["search_volume"]):
                        preserved_seeds = current["seed_keywords"]
                        preserved_score = current["seed_score"]
                        current.update(parsed)
                        current["seed_keywords"] = preserved_seeds
                        current["seed_score"] = preserved_score

        for row in aggregated.values():
            ordered_seeds = sorted(row.pop("seed_keywords"), key=normalize_keyword)
            row["seed_keyword"] = max(ordered_seeds, key=lambda value: _seed_relevance(row["keyword"], value), default="")
            row["seed_keywords"] = ordered_seeds
            row["seed_count"] = len(ordered_seeds)
            row["seed_score"] = max(
                row["seed_score"],
                max((seed_scores.get(normalize_keyword(value), 0.0) for value in ordered_seeds), default=0.0),
            )
        result.candidates = list(aggregated.values())
        return result

    def _request_chunk(
        self,
        chunk: list[SeedChoice],
        chunk_index: int,
        result: CollectionResult,
    ) -> dict[str, Any] | None:
        method = self.config["method"]
        uri = self.config["uri"]
        params = {
            "hintKeywords": ",".join(_wire_keyword(choice.keyword) for choice in chunk),
            "showDetail": self.config["show_detail"],
        }
        last_status: Any = "EXCEPTION"
        last_error = ""
        last_attempt = 0
        max_attempts = self.config["max_retries"] + 1
        for attempt in range(1, max_attempts + 1):
            last_attempt = attempt
            timestamp = str(round(self.clock() * 1000))
            headers = {
                "X-Timestamp": timestamp,
                "X-API-KEY": self.credentials.api_key,
                "X-Customer": str(self.credentials.customer_id),
                "X-Signature": make_signature(timestamp, method, uri, self.credentials.secret_key),
            }
            try:
                response = self.session.get(
                    self.config["base_url"] + uri,
                    params=params,
                    headers=headers,
                    timeout=self.config["timeout_seconds"],
                )
                result.api_calls += 1
                last_status = response.status_code
                if response.status_code == 200:
                    return response.json()
                last_error = getattr(response, "text", "")[: self.config["error_text_limit"]]
                retryable = response.status_code == 429 or response.status_code >= 500
                if not retryable:
                    break
            except Exception as exc:
                result.api_calls += 1
                last_error = str(exc)
            if attempt < max_attempts:
                self.sleeper(self.config["backoff_base_seconds"] * (2 ** (attempt - 1)))
        result.failures.append({
            "chunk": chunk_index,
            "seed_keywords": ", ".join(choice.keyword for choice in chunk),
            "status": last_status,
            "error": last_error,
            "attempts": last_attempt,
        })
        return None


def _numeric_or_negative(value: Any) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else -1.0
    except (TypeError, ValueError):
        return -1.0


def _seed_relevance(keyword: str, seed: str) -> tuple[int, int, int]:
    keyword_compact = normalize_keyword(keyword).replace(" ", "")
    seed_compact = normalize_keyword(seed).replace(" ", "")
    containment = int(keyword_compact in seed_compact or seed_compact in keyword_compact)
    overlap = len(set(normalize_keyword(keyword).split()) & set(normalize_keyword(seed).split()))
    return containment, overlap, -abs(len(keyword_compact) - len(seed_compact))

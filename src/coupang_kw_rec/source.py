"""Read seed lists and core workbook inputs without importing the core package."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from difflib import SequenceMatcher
import json
from pathlib import Path
from typing import Any

from .kwnorm import normalize_keyword


@dataclass
class InputData:
    direct_seeds: list[str] = field(default_factory=list)
    keyword_rows: list[dict[str, Any]] = field(default_factory=list)
    converting_rows: list[dict[str, Any]] = field(default_factory=list)
    token_rows: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def read_seed_file(path: str | Path) -> list[str]:
    source = Path(path)
    if source.suffix.casefold() == ".csv":
        with source.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        values = [row[0].strip() for row in rows if row and row[0].strip()]
        if values and normalize_keyword(values[0]) in {"keyword", "키워드"}:
            values = values[1:]
    else:
        values = [line.strip() for line in source.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = normalize_keyword(value)
        if key and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _best_column(columns: list[str], aliases: list[str], threshold: float) -> tuple[str | None, bool]:
    normalized = {normalize_keyword(column): column for column in columns}
    for alias in aliases:
        if normalize_keyword(alias) in normalized:
            return normalized[normalize_keyword(alias)], False
    choices = [
        (SequenceMatcher(None, normalize_keyword(alias), normalize_keyword(column)).ratio(), column)
        for alias in aliases for column in columns
    ]
    if not choices:
        return None, False
    score, column = max(choices)
    return (column, True) if score >= threshold else (None, False)


def _canonicalize(frame, aliases: dict[str, list[str]], threshold: float, warnings: list[str], sheet: str):
    rename: dict[str, str] = {}
    for canonical, candidates in aliases.items():
        found, fuzzy = _best_column([str(column) for column in frame.columns], candidates, threshold)
        if found:
            rename[found] = canonical
            if fuzzy:
                warnings.append(f"{sheet}: '{found}' 열을 '{canonical}'로 유사 탐지했습니다.")
    return frame.rename(columns=rename)


def read_core_workbook(path: str | Path, config: dict[str, Any]) -> InputData:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("엑셀 입력에는 pandas와 openpyxl이 필요합니다.") from exc
    source = Path(path)
    result = InputData()
    contract = source.with_name(config["source"]["contract_filename"])
    if contract.exists():
        try:
            payload = json.loads(contract.read_text(encoding="utf-8"))
            if payload.get("schema_version") not in config["source"]["supported_schema_versions"]:
                result.warnings.append(f"지원하지 않는 contract schema_version: {payload.get('schema_version')}")
        except (OSError, json.JSONDecodeError) as exc:
            result.warnings.append(f"contract.json 확인 실패: {exc}")
    else:
        result.warnings.append("contract.json이 없어 유사 컬럼 탐지를 사용합니다.")

    book = pd.ExcelFile(source)
    specs = config["source"]["sheets"]
    targets = {
        "keyword": "keyword_rows",
        "converting": "converting_rows",
        "token": "token_rows",
    }
    for kind, attribute in targets.items():
        sheet = specs[kind]
        if sheet not in book.sheet_names:
            result.warnings.append(f"시트 없음: {sheet}")
            continue
        frame = pd.read_excel(source, sheet_name=sheet)
        frame = _canonicalize(
            frame,
            config["source"]["column_aliases"],
            config["source"]["fuzzy_threshold"],
            result.warnings,
            sheet,
        )
        setattr(result, attribute, frame.to_dict(orient="records"))
    return result

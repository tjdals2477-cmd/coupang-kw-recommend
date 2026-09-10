"""Excel and CSV report generation for keyword recommendations."""

from __future__ import annotations

import csv
from datetime import datetime
import io
import math
from pathlib import Path
from typing import Any

from .pipeline import PipelineResult


def build_workbook_bytes(result: PipelineResult, config: dict[str, Any]) -> bytes:
    import xlsxwriter

    buffer = io.BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {"in_memory": True, "nan_inf_to_errors": False})
    formats = _formats(workbook)
    _write_summary(workbook, result, config, formats)
    _write_recommendations(workbook, result.recommendations, config, formats)
    _write_brand_sheet(workbook, result.recommendations, config, formats)
    _write_simple_sheet(workbook, config["output"]["sheets"]["held"], result.filters.held, config["output"]["held_columns"], formats)
    _write_simple_sheet(workbook, config["output"]["sheets"]["failures"], result.collection.failures, config["output"]["failure_columns"], formats)
    _write_simple_sheet(workbook, config["output"]["sheets"]["reverse"], result.filters.reverse_excludes, config["output"]["reverse_columns"], formats)
    workbook.close()
    return buffer.getvalue()


def write_outputs(result: PipelineResult, config: dict[str, Any], out_dir: str | Path) -> dict[str, Path]:
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    output = config["output"]
    workbook_path = target / f"{output['workbook_prefix']}{datetime.now():%Y%m%d}.xlsx"
    workbook_path.write_bytes(build_workbook_bytes(result, config))
    paths = {
        "workbook": workbook_path,
        "recommend": target / output["recommend_csv"],
        "full": target / output["full_csv"],
        "exclude": target / output["exclude_csv"],
    }
    export_grades = set(output["recommend_export_grades"])
    _write_csv(paths["recommend"], [{"keyword": row["keyword"]} for row in result.recommendations if row["rec_grade"] in export_grades], ["keyword"])
    _write_csv(paths["full"], result.recommendations, output["recommendation_columns"])
    _write_csv(paths["exclude"], [{"keyword": row["keyword"]} for row in result.filters.reverse_excludes], ["keyword"])
    return paths


def _formats(workbook):
    return {
        "title": workbook.add_format({"font_name": "Arial", "font_size": 15, "bold": True, "font_color": "#172B4D"}),
        "header": workbook.add_format({"font_name": "Arial", "font_size": 10, "bold": True, "font_color": "#FFFFFF", "bg_color": "#1F4E78", "align": "center", "valign": "vcenter", "border": 0}),
        "body": workbook.add_format({"font_name": "Arial", "font_size": 10, "font_color": "#222222", "valign": "vcenter"}),
        "number": workbook.add_format({"font_name": "Arial", "font_size": 10, "num_format": "#,##0", "valign": "vcenter"}),
        "decimal": workbook.add_format({"font_name": "Arial", "font_size": 10, "num_format": "0.000", "valign": "vcenter"}),
        "percent": workbook.add_format({"font_name": "Arial", "font_size": 10, "num_format": "0.00%", "valign": "vcenter"}),
        "section": workbook.add_format({"font_name": "Arial", "font_size": 10, "bold": True, "font_color": "#172B4D", "bg_color": "#D9EAF7"}),
        "warning": workbook.add_format({"font_name": "Arial", "font_size": 10, "font_color": "#9C5700", "bg_color": "#FFF2CC", "text_wrap": True}),
    }


def _setup_sheet(sheet, tab_color: str | None = None):
    sheet.hide_gridlines(2)
    if tab_color:
        sheet.set_tab_color(tab_color)
    sheet.set_default_row(18)


def _write_summary(workbook, result: PipelineResult, config: dict[str, Any], formats: dict[str, Any]) -> None:
    sheet = workbook.add_worksheet(config["output"]["sheets"]["summary"])
    _setup_sheet(sheet, "#1F4E78")
    sheet.set_column("A:A", 27)
    sheet.set_column("B:B", 80)
    sheet.write("A2", "쿠팡 추천 키워드 요약", formats["title"])
    row = 3
    summary = [
        ("생성시각", datetime.now().isoformat(timespec="seconds")),
        ("선정 시드", len(result.seeds)),
        ("API 청크", result.collection.total_chunks),
        ("성공 청크", result.collection.successful_chunks),
        ("실패 청크", len(result.collection.failures)),
        ("실제 API 호출", result.collection.api_calls),
        ("캐시 적중률", result.collection.cache_hits / result.collection.total_chunks if result.collection.total_chunks else 0.0),
        ("필터 통과", len(result.filters.candidates)),
        ("최종 추천", len(result.recommendations)),
        ("상한으로 잘림", result.trimmed_count),
    ]
    sheet.write_row(row, 0, ["항목", "값"], formats["header"])
    row += 1
    for label, value in summary:
        fmt = formats["percent"] if label == "캐시 적중률" else formats["body"]
        sheet.write(row, 0, label, formats["body"])
        sheet.write(row, 1, value, fmt)
        row += 1
    row += 1
    sheet.write(row, 0, "선정 시드와 근거", formats["section"])
    row += 1
    sheet.write_row(row, 0, ["시드", "근거 / 점수"], formats["header"])
    row += 1
    for seed in result.seeds:
        sheet.write(row, 0, seed.keyword, formats["body"])
        sheet.write(row, 1, f"{seed.reason} / {seed.seed_score:g}", formats["body"])
        row += 1
    row += 1
    sheet.write(row, 0, "단계별 탈락", formats["section"])
    row += 1
    for stage, count in result.filters.stage_counts.items():
        sheet.write_row(row, 0, [stage, count], formats["body"])
        row += 1
    row += 1
    sheet.write(row, 0, "점수 가중치", formats["section"])
    row += 1
    for key in config["scoring"]["weight_keys"]:
        sheet.write_row(row, 0, [key, config["scoring"][key]], formats["body"])
        row += 1
    row += 1
    sheet.write(row, 0, "주의", formats["section"])
    row += 1
    for notice in config["output"]["notices"]:
        sheet.merge_range(row, 0, row, 1, notice, formats["warning"])
        sheet.set_row(row, 34)
        row += 1
    for warning in result.warnings:
        sheet.merge_range(row, 0, row, 1, f"데이터 품질 경고: {warning}", formats["warning"])
        row += 1
    sheet.freeze_panes(3, 0)


def _write_recommendations(workbook, rows: list[dict[str, Any]], config: dict[str, Any], formats: dict[str, Any]) -> None:
    name = config["output"]["sheets"]["recommendations"]
    columns = config["output"]["recommendation_columns"]
    sheet = workbook.add_worksheet(name)
    _setup_sheet(sheet, "#1F4E78")
    _write_table(sheet, rows, columns, formats)
    grade_col = columns.index("rec_grade")
    if rows:
        sheet.conditional_format(1, grade_col, len(rows), grade_col, {"type": "text", "criteria": "containing", "value": "REC_A", "format": workbook.add_format({"bg_color": "#E2F0D9", "font_color": "#375623"})})


def _write_brand_sheet(workbook, rows: list[dict[str, Any]], config: dict[str, Any], formats: dict[str, Any]) -> None:
    name = config["output"]["sheets"]["brands"]
    columns = config["output"]["brand_columns"]
    sheet = workbook.add_worksheet(name)
    _setup_sheet(sheet)
    output_rows: list[dict[str, Any]] = []
    for brand in config["brands"]["own"]:
        matching = [row for row in rows if row.get("brand") == brand]
        if matching:
            output_rows.extend({**row, "status": "추천 있음"} for row in matching)
        else:
            output_rows.append({"brand": brand, "status": "인지도 미형성"})
    _write_table(sheet, output_rows, columns, formats)


def _write_simple_sheet(workbook, name: str, rows: list[dict[str, Any]], columns: list[str], formats: dict[str, Any]) -> None:
    sheet = workbook.add_worksheet(name)
    _setup_sheet(sheet)
    _write_table(sheet, rows, columns, formats)


def _write_table(sheet, rows: list[dict[str, Any]], columns: list[str], formats: dict[str, Any]) -> None:
    sheet.write_row(0, 0, columns, formats["header"])
    for row_index, row in enumerate(rows, start=1):
        for column_index, column in enumerate(columns):
            value = row.get(column, "")
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            if isinstance(value, float) and math.isnan(value):
                value = ""
            fmt = _column_format(column, formats)
            sheet.write(row_index, column_index, value, fmt)
    if columns:
        sheet.autofilter(0, 0, max(0, len(rows)), len(columns) - 1)
        sheet.freeze_panes(1, 1)
        for index, column in enumerate(columns):
            width = min(36, max(10, len(column) + 3, *(len(str(row.get(column, ""))) + 2 for row in rows[:100])))
            sheet.set_column(index, index, width)


def _column_format(column: str, formats: dict[str, Any]):
    if column in {"mobile_ratio", "naver_avg_ctr", "relevance"}:
        return formats["percent"]
    if column in {"search_volume", "pc_qc", "mobile_qc", "seed_count", "rank"}:
        return formats["number"]
    if column in {"score", "pl_avg_depth", "seed_roas"}:
        return formats["decimal"]
    return formats["body"]


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({column: _csv_value(row.get(column, "")) for column in columns} for row in rows)


def _csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if isinstance(value, float) and math.isnan(value):
        return ""
    return value

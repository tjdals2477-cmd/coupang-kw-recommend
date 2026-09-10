"""Streamlit user interface."""

from __future__ import annotations

import hmac
import math
import os
from pathlib import Path
import tempfile

from .config import load_config
from .naver_api import Credentials
from .pipeline import run_pipeline
from .report import write_outputs
from .seed import select_seeds
from .source import InputData, read_core_workbook


RESULT_COLUMN_LABELS = {
    "rank": "순위",
    "keyword": "추천 키워드",
    "rec_grade": "추천 등급",
    "action_ko": "추천 행동",
    "score": "추천 종합점수(100점)",
    "search_volume": "월간 총검색량",
    "pc_qc": "PC 검색량",
    "mobile_qc": "모바일 검색량",
    "mobile_ratio": "모바일 비중(%)",
    "comp_idx": "광고 경쟁도",
    "pl_avg_depth": "평균 광고 노출 개수",
    "naver_avg_ctr": "네이버 평균 클릭률(%)",
    "seed_keyword": "연결된 기준 키워드",
    "seed_count": "연결 기준어 수",
    "seed_roas": "기준 키워드 ROAS",
    "relevance": "상품명 연관도(%)",
    "brand": "브랜드 구분",
    "already_converting": "기존 전환 키워드",
    "note": "참고 사항",
}

GRADE_LABELS = {
    "REC_A_즉시등록": "A · 바로 등록",
    "REC_B_테스트": "B · 소액 테스트",
    "REC_C_관찰": "C · 관찰",
    "REC_BRAND": "브랜드 · 우선 등록",
}


def _display_value(column: str, value):
    if isinstance(value, float) and math.isnan(value):
        return "-"
    if column in {"mobile_ratio", "relevance"} and isinstance(value, (int, float)):
        return round(value * 100, 1)
    if column == "rec_grade":
        return GRADE_LABELS.get(str(value), value)
    if column == "brand" and value in {None, "", "NONE"}:
        return "일반 키워드"
    if column == "already_converting":
        return "예" if value else "아니오"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return value


def recommendations_for_display(rows: list[dict]) -> list[dict]:
    """Return UI-only Korean labels without changing Excel/CSV contracts."""
    numeric_scores = [
        float(row["score"])
        for row in rows
        if isinstance(row.get("score"), (int, float)) and not math.isnan(float(row["score"]))
    ]
    score_min = min(numeric_scores, default=0.0)
    score_max = max(numeric_scores, default=0.0)

    def display_row(row: dict) -> dict:
        displayed: dict = {}
        for column, label in RESULT_COLUMN_LABELS.items():
            value = row.get(column, "")
            if column == "score" and isinstance(value, (int, float)) and not math.isnan(float(value)):
                value = 100.0 if score_max == score_min else (float(value) - score_min) / (score_max - score_min) * 100
                displayed[label] = round(value, 1)
            else:
                displayed[label] = _display_value(column, value)
        return displayed

    return [
        display_row(row)
        for row in rows
    ]


def _streamlit_secret(st, name: str) -> str:
    try:
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


def _require_app_password(st) -> bool:
    """Render a password gate so a public deployment stays personal."""
    expected = _streamlit_secret(st, "APP_PASSWORD") or os.getenv("APP_PASSWORD", "").strip()
    if not expected:
        st.error("앱 비밀번호가 아직 설정되지 않았습니다. Streamlit Secrets에 APP_PASSWORD를 넣어주세요.")
        return False
    if st.session_state.get("authenticated") is True:
        return True

    st.title("🔒 쿠팡 키워드 추천")
    st.caption("주인만 들어갈 수 있는 비밀번호 문입니다.")
    supplied = st.text_input("앱 비밀번호", type="password")
    if st.button("문 열기", type="primary"):
        if hmac.compare_digest(supplied, expected):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("비밀번호가 맞지 않습니다.")
    return False


def _credentials_from_streamlit(st) -> Credentials:
    from_env = Credentials.from_env()
    return Credentials(
        _streamlit_secret(st, "NAVER_AD_API_KEY") or from_env.api_key,
        _streamlit_secret(st, "NAVER_AD_SECRET_KEY") or from_env.secret_key,
        _streamlit_secret(st, "NAVER_AD_CUSTOMER_ID") or from_env.customer_id,
    )


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="쿠팡 키워드 추천", page_icon="🔎", layout="wide")
    if not _require_app_password(st):
        return
    st.title("쿠팡 키워드 추천")
    st.caption("상품명이나 핵심 키워드를 넣으면 네이버 검색광고 데이터를 바탕으로 최대 500개를 정리합니다.")

    config = load_config()
    with st.sidebar:
        st.subheader("설정")
        limit = st.slider("추천 개수", 1, config["output"]["limit_max"], config["output"]["limit_default"])
        offline = st.checkbox("오프라인 모드", help="저장된 캐시만 사용하며 네트워크를 전혀 호출하지 않습니다.")
        seed_only = st.checkbox("시드만 확인", help="네이버 API를 호출하지 않고 시작 키워드만 확인합니다.")
        st.caption("API 열쇠는 Streamlit Secrets 또는 로컬 .env에서만 읽습니다.")

    seeds_text = st.text_area(
        "상품명 또는 핵심 키워드",
        height=170,
        placeholder="한 줄에 하나씩 입력하세요.\n예: 데이온 LED 일자등 30W 주광색",
    )
    source_upload = st.file_uploader("코어 분석 엑셀 (선택)", type=["xlsx"])
    contract_upload = st.file_uploader("contract.json (선택)", type=["json"], help="코어 엑셀과 함께 생성된 contract.json이 있다면 올려주세요.")
    exclude_upload = st.file_uploader("제외키워드 CSV/TXT (선택)", type=["csv", "txt"])

    if not st.button("추천 시작", type="primary", width="stretch"):
        st.info("위 칸에 상품명을 입력하고 ‘추천 시작’을 누르세요.")
        return

    direct_seeds = [line.strip() for line in seeds_text.splitlines() if line.strip()]
    if not direct_seeds and source_upload is None:
        st.error("상품명을 한 줄 이상 입력하거나 코어 분석 엑셀을 올려주세요.")
        return

    with tempfile.TemporaryDirectory() as temporary:
        temp = Path(temporary)
        data = InputData(direct_seeds=direct_seeds)
        if source_upload is not None:
            source_path = temp / "source.xlsx"
            source_path.write_bytes(source_upload.getvalue())
            if contract_upload is not None:
                (temp / config["source"]["contract_filename"]).write_bytes(contract_upload.getvalue())
            workbook_data = read_core_workbook(source_path, config)
            workbook_data.direct_seeds.extend(direct_seeds)
            data = workbook_data
        exclusions: list[str] = []
        if exclude_upload is not None:
            content = exclude_upload.getvalue().decode("utf-8-sig", errors="replace")
            exclusions = [line.split(",", 1)[0].strip() for line in content.splitlines() if line.strip()]

        seeds = select_seeds(data, config)
        if seed_only:
            st.success(f"시드 {len(seeds)}개를 골랐습니다. 네트워크 호출은 0회입니다.")
            st.dataframe(
                [{"기준 키워드": seed.keyword, "선정 이유": seed.reason, "기준 점수": seed.seed_score} for seed in seeds],
                width="stretch",
                hide_index=True,
            )
            return

        credentials = _credentials_from_streamlit(st)
        if not offline and not credentials.complete:
            st.error("네이버 API 열쇠가 없습니다. Streamlit 앱 설정의 Secrets에 3개 값을 먼저 넣어주세요.")
            st.code('NAVER_AD_API_KEY="..."\nNAVER_AD_SECRET_KEY="..."\nNAVER_AD_CUSTOMER_ID="..."')
            return

        with st.spinner("연관 키워드를 모으고 정리하고 있습니다..."):
            result = run_pipeline(data, exclusions, config, credentials, limit, offline=offline)
            output_dir = temp / "output"
            paths = write_outputs(result, config, output_dir)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("최종 추천", len(result.recommendations))
        col2.metric("보류", len(result.filters.held))
        col3.metric("역제안", len(result.filters.reverse_excludes))
        col4.metric("실패 청크", len(result.collection.failures))

        if result.recommendations:
            st.subheader("추천 결과")
            st.caption("추천 종합점수는 네이버 검색량·클릭률·경쟁도·상품명 연관도를 합쳐 100점 만점으로 환산한 값입니다. 점수와 연관도는 높을수록, 광고 경쟁도는 낮을수록 유리합니다.")
            st.dataframe(
                recommendations_for_display(result.recommendations),
                width="stretch",
                hide_index=True,
                column_config={
                    "추천 종합점수(100점)": st.column_config.NumberColumn(
                        format="%.1f점",
                        help="네이버 데이터와 상품명 연관도를 합쳐 현재 추천 결과 안에서 0~100점으로 환산한 내부 점수입니다.",
                    ),
                    "월간 총검색량": st.column_config.NumberColumn(format="%d회"),
                    "PC 검색량": st.column_config.NumberColumn(format="%d회"),
                    "모바일 검색량": st.column_config.NumberColumn(format="%d회"),
                    "모바일 비중(%)": st.column_config.NumberColumn(format="%.1f%%"),
                    "네이버 평균 클릭률(%)": st.column_config.NumberColumn(
                        format="%.2f%%",
                        help="네이버 검색광고 키워드 도구가 제공하는 PC·모바일 월평균 클릭률의 평균입니다.",
                    ),
                    "상품명 연관도(%)": st.column_config.NumberColumn(format="%.1f%%"),
                },
            )
        else:
            st.warning("추천 결과가 없습니다. 필터 설정, API 열쇠 또는 오프라인 캐시를 확인하세요.")
        if result.collection.failures:
            with st.expander("수집 실패 보기"):
                st.dataframe(result.collection.failures, width="stretch", hide_index=True)

        st.subheader("파일 받기")
        downloads = st.columns(4)
        labels = {
            "workbook": ("엑셀 보고서", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            "recommend": ("등록용 CSV", "text/csv"),
            "full": ("전체 CSV", "text/csv"),
            "exclude": ("역제안 CSV", "text/csv"),
        }
        for column, (key, path) in zip(downloads, paths.items()):
            label, mime = labels[key]
            column.download_button(label, path.read_bytes(), file_name=path.name, mime=mime, width="stretch")


if __name__ == "__main__":
    main()

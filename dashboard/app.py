# dashboard/app.py

import re
from pathlib import Path
from typing import Tuple

import pandas as pd
import streamlit as st
import math

# ──────────────────────────────────────────────────────────────
# 기본 설정
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Darkweb Leak Intelligence Dashboard",
    layout="wide",
)

st.markdown(
    """
    <style>
    .main > div {
        padding-top: 1rem;
        padding-bottom: 2rem;
    }
    section[data-testid="stSidebar"] > div {
        padding-top: 1rem;
    }
    .small-text {
        font-size: 0.85rem;
        color: #888888;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# 데이터 파일 위치 설정 (프로젝트 루트 기준: /data/leak_records.csv)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CSV_PATH = DATA_DIR / "leak_records.csv"


# ──────────────────────────────────────────────────────────────
# 대시보드 스키마(고정)
# ──────────────────────────────────────────────────────────────
# storage.py의 CSV_HEADER와 호환
CSV_HEADER = [
    "source",
    "post_title",
    "target_service",
    "domains",
    "leak_types",
    "estimated_volume",
    "confidence",
    "collected_at",
    "post_id",
    "message_url",
]

# 대시보드에서 내부적으로도 쓰는 컬럼(없으면 생성)
DASHBOARD_EXTRA_COLS = [
    "posted_at",   # storage.csv에는 없을 수 있음 → 항상 존재하게 만들기
    "threat_claim",
]


def _coerce_str_series(df: pd.DataFrame, col: str) -> None:
    df[col] = df[col].fillna("").astype(str)


def ensure_dashboard_schema(df: pd.DataFrame) -> pd.DataFrame:
    """
    CSV에서 로드한 df를 대시보드용으로 '항상 동일한 스키마'로 보정한다.
    - 누락 컬럼 생성
    - 타입 정리(특히 estimated_volume 숫자, 날짜 파싱)
    - confidence 기본값 보정
    """
    if df is None or df.empty:
        # 빈 DF라도 헤더는 갖고 있게 해서 이후 로직이 깨지지 않게
        df = pd.DataFrame(columns=CSV_HEADER + DASHBOARD_EXTRA_COLS)

    # 1) 필수 컬럼 생성
    for col in CSV_HEADER:
        if col not in df.columns:
            df[col] = ""

    # 2) 대시보드용 추가 컬럼 생성
    for col in DASHBOARD_EXTRA_COLS:
        if col not in df.columns:
            df[col] = ""

    # 3) 문자열 컬럼 정리
    for col in ["source", "confidence", "post_title", "target_service", "domains", "leak_types", "post_id", "message_url", "threat_claim"]:
        _coerce_str_series(df, col)

    # 4) volume 숫자형 캐스팅 (정렬/위험도 계산용)
    df["estimated_volume"] = pd.to_numeric(df["estimated_volume"], errors="coerce")

    # 5) 날짜 캐스팅 (없거나 이상해도 coerce)
    df["collected_at"] = pd.to_datetime(df["collected_at"], errors="coerce")
    df["posted_at"] = pd.to_datetime(df["posted_at"], errors="coerce")

    # 6) confidence 기본값 (빈 값이면 medium)
    conf = df["confidence"].str.strip().str.lower()
    df.loc[conf == "", "confidence"] = "medium"

    # 7) 표 컬럼 순서 고정(가독성 + 디버깅 용이)
    ordered_cols = CSV_HEADER + DASHBOARD_EXTRA_COLS
    df = df[ordered_cols]

    return df


# ──────────────────────────────────────────────────────────────
# 데이터 로딩
# ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_data() -> pd.DataFrame:
    """CSV에서 LeakRecord 데이터를 로드한다."""
    if not CSV_PATH.exists():
        return ensure_dashboard_schema(pd.DataFrame())

    # dtype=str로 읽으면 NaN/타입 흔들림이 줄어듦
    df = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False)
    return ensure_dashboard_schema(df)


# ──────────────────────────────────────────────────────────────
# 위험도 계산
# ──────────────────────────────────────────────────────────────
def compute_risk_score(row: pd.Series) -> Tuple[int, str, str]:
    """
    confidence + estimated_volume 기반 위험도 점수/라벨/아이콘 계산.
    점수(total), 라벨, 색상아이콘(이모지) 반환.
    """
    conf = str(row.get("confidence", "")).lower()

    if conf == "high":
        base = 3
    elif conf == "medium":
        base = 2
    elif conf == "low":
        base = 1
    else:
        base = 1

    vol = row.get("estimated_volume", 0)
    if pd.isna(vol):
        vol = 0

    if vol >= 1_000_000:
        vol_score = 3
    elif vol >= 100_000:
        vol_score = 2
    elif vol > 0:
        vol_score = 1
    else:
        vol_score = 0

    total = base + vol_score  # 0 ~ 6

    if total >= 5:
        label = "위험도 매우 높음"
        color = "🔴"
    elif total >= 3:
        label = "위험도 높음"
        color = "🟠"
    elif total >= 2:
        label = "위험도 보통"
        color = "🟡"
    else:
        label = "위험도 낮음"
        color = "🟢"

    return total, label, color


def add_risk_info(df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame에 risk_score / risk_label / risk_indicator 컬럼을 추가."""
    if df.empty:
        return df

    df = df.copy()
    scores = df.apply(compute_risk_score, axis=1, result_type="expand")
    df["risk_score"] = scores[0]
    df["risk_label"] = scores[1]
    df["risk_indicator"] = scores[2]
    return df


def split_csv_list_cell(value: str) -> list[str]:
    """'a, b, c' 형태를 ['a','b','c']로 안전하게 분리."""
    if value is None:
        return []
    s = str(value).strip()
    if not s:
        return []
    return [t.strip() for t in s.split(",") if t.strip()]


# ──────────────────────────────────────────────────────────────
# 메인 앱
# ──────────────────────────────────────────────────────────────
def main() -> None:
    st.title("🌙 Darkweb Leak Intelligence Dashboard")
    st.markdown(
        '<p class="small-text">'
        "텔레그램 기반 다크웹 유출 정보 자동 수집 · 분석 대시보드"
        "</p>",
        unsafe_allow_html=True,
    )

    df = load_data()

    if st.button("데이터 새로고침"):
        load_data.clear()
        st.experimental_rerun()

    # 스키마가 이미 보정되어 있으므로 df.empty만 확인하면 됨
    if df.empty:
        st.warning("현재 data/leak_records.csv 파일이 없거나, 데이터가 비어 있습니다.")
        return

    df = add_risk_info(df)

    # ───────────── 사이드바: 검색 · 필터 · 정렬 ─────────────
    st.sidebar.header("검색 / 필터")

    # 1) 검색
    st.sidebar.subheader("검색(Search)")
    q_title = st.sidebar.text_input("제목 검색 (post_title)")
    q_domain = st.sidebar.text_input("도메인 검색 (domains)")
    q_target = st.sidebar.text_input("타겟 서비스 검색 (target_service)")
    q_source = st.sidebar.text_input("소스/채널 검색 (source)")
    q_any = st.sidebar.text_input("키워드 검색 (모든 텍스트 필드)")

    df_filtered = df.copy()

    if q_title:
        df_filtered = df_filtered[
            df_filtered["post_title"].str.contains(q_title, case=False, na=False)
        ]

    if q_domain:
        df_filtered = df_filtered[
            df_filtered["domains"].str.contains(q_domain, case=False, na=False)
        ]

    if q_target:
        df_filtered = df_filtered[
            df_filtered["target_service"].str.contains(q_target, case=False, na=False)
        ]

    if q_source:
        df_filtered = df_filtered[
            df_filtered["source"].str.contains(q_source, case=False, na=False)
        ]

    if q_any:
        text_cols = df_filtered.select_dtypes(include=["object"]).columns
        if len(text_cols) > 0:
            df_tmp = df_filtered.copy()
            df_tmp["_concat"] = df_tmp[text_cols].fillna("").astype(str).agg(" ".join, axis=1)
            df_filtered = df_tmp[df_tmp["_concat"].str.contains(q_any, case=False, na=False)].drop(columns=["_concat"])

    # 2) 필터
    st.sidebar.subheader("필터(Filter)")

    # leak_types 필터 (항상 컬럼 존재)
    all_leak_types: list[str] = []
    for v in df["leak_types"].astype(str):
        all_leak_types.extend(split_csv_list_cell(v))

    leak_type_values = sorted(set(all_leak_types))
    selected_leak_types = st.sidebar.multiselect("Leak Types", leak_type_values)

    if selected_leak_types:
        pattern = "|".join([re.escape(t) for t in selected_leak_types])
        df_filtered = df_filtered[
            df_filtered["leak_types"].astype(str).str.contains(pattern, na=False)
        ]

    # confidence 필터 (항상 컬럼 존재)
    confidence_values = sorted(df["confidence"].astype(str).str.lower().unique().tolist())
    selected_confidence = st.sidebar.multiselect("Confidence", confidence_values)
    if selected_confidence:
        df_filtered = df_filtered[df_filtered["confidence"].astype(str).str.lower().isin(selected_confidence)]

    # 날짜 범위 필터 (collected_at / posted_at) — 항상 존재하게 보정됨
    st.sidebar.markdown("---")
    st.sidebar.write("날짜 범위 필터")

    available_date_fields = ["collected_at", "posted_at"]
    date_field = st.sidebar.selectbox("기준 날짜 컬럼", available_date_fields, index=0)

    min_date = df[date_field].min()
    max_date = df[date_field].max()

    # 날짜가 전부 NaT면 범위 선택 UI 대신 안내
    if pd.isna(min_date) or pd.isna(max_date):
        st.sidebar.caption("선택한 날짜 컬럼에 유효한 값이 없어 날짜 필터를 적용할 수 없습니다.")
    else:
        start_date, end_date = st.sidebar.date_input(
            f"{date_field} 범위",
            value=[min_date.date(), max_date.date()],
        )
        if start_date and end_date:
            mask = (df_filtered[date_field] >= pd.to_datetime(start_date)) & (
                df_filtered[date_field] <= pd.to_datetime(end_date)
            )
            df_filtered = df_filtered[mask]

    # 3) 정렬
    st.sidebar.markdown("---")
    st.sidebar.subheader("정렬(Sort)")

    sort_options = [
        "정렬 없음",
        "최신순 (collected_at desc)",
        "최신순 (posted_at desc)",
        "volume 큰 순",
        "source 알파벳 순",
        "위험도 높은 순 (risk_score desc)",
    ]

    sort_key = st.sidebar.selectbox("정렬 기준", sort_options)

    if sort_key == "최신순 (posted_at desc)":
        df_filtered = df_filtered.sort_values("posted_at", ascending=False)
    elif sort_key == "최신순 (collected_at desc)":
        df_filtered = df_filtered.sort_values("collected_at", ascending=False)
    elif sort_key == "volume 큰 순":
        df_filtered = df_filtered.sort_values("estimated_volume", ascending=False, na_position="last")
    elif sort_key == "source 알파벳 순":
        df_filtered = df_filtered.sort_values("source", ascending=True)
    elif sort_key == "위험도 높은 순 (risk_score desc)":
        df_filtered = df_filtered.sort_values("risk_score", ascending=False)

    # ───────────── 상단 KPI 영역 ─────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("전체 레코드 수", len(df))
    with col2:
        st.metric("현재 필터된 레코드 수", len(df_filtered))
    with col3:
        st.metric("소스(채널) 개수", df["source"].nunique())

    # ───────────── 시각화 영역 (matplotlib 없이) ─────────────
    st.markdown("## 📈 통계 / 시각화")

    if df_filtered.empty:
        st.info("현재 조건에 해당하는 레코드가 없습니다.")
    else:
        col_g1, col_g2 = st.columns(2)

        with col_g1:
            # 날짜별 건수 추이: Streamlit line_chart 사용
            date_field_for_chart = date_field if date_field in ["posted_at", "collected_at"] else "collected_at"

            df_time = df_filtered.copy()
            df_time[date_field_for_chart] = pd.to_datetime(df_time[date_field_for_chart], errors="coerce")
            df_time = df_time.dropna(subset=[date_field_for_chart])

            st.subheader("날짜별 누출 건수 추이")
            if not df_time.empty:
                daily_counts = (
                    df_time.groupby(df_time[date_field_for_chart].dt.date)
                    .size()
                    .reset_index(name="count")
                )
                daily_counts = daily_counts.rename(columns={daily_counts.columns[0]: "date"}).set_index("date")
                st.line_chart(daily_counts["count"])
            else:
                st.write("날짜 정보가 없어 트렌드 차트를 표시할 수 없습니다.")

        with col_g2:
            # 채널별 누출 비중: Streamlit bar_chart 사용
            st.subheader("채널별 누출 건수 (source 기준)")
            channel_counts = df_filtered["source"].astype(str).value_counts()
            st.bar_chart(channel_counts)

        # Leak Types 비율: bar_chart
        st.subheader("Leak Types (count)")
        all_types: list[str] = []
        for v in df_filtered["leak_types"].astype(str):
            all_types.extend(split_csv_list_cell(v))

        if all_types:
            type_counts = pd.Series(all_types).value_counts()
            st.bar_chart(type_counts)
        else:
            st.write("Leak Types 데이터가 없습니다.")

    # ───────────── 레코드 테이블 + 상세 보기 ─────────────
    st.markdown("## 📄 Leak Records")

    # id 컬럼은 원래 CSV에 없으므로 post_id를 기본 키로 삼는다
    df_table = df_filtered.copy()
    df_table["id"] = df_table["post_id"].astype(str)
    # post_id가 비어있으면 index를 fallback
    missing = df_table["id"].str.strip() == ""
    if missing.any():
        df_table.loc[missing, "id"] = df_table.loc[missing].reset_index()["index"].astype(str).values

    columns_for_table = [
        "id",
        "risk_indicator",
        "risk_label",
        "confidence",
        "estimated_volume",
        "post_title",
        "source",
        "domains",
        "leak_types",
        "posted_at",
        "collected_at",
    ]
    # 현재 df_table에는 모두 존재(ensure_dashboard_schema + add_risk_info로 보장)
    st.dataframe(df_table[columns_for_table], use_container_width=True, hide_index=True)

    record_ids = df_table["id"].astype(str).tolist()
    if record_ids:
        selected_id = st.selectbox("상세 보기할 레코드 선택 (id)", record_ids)

        detail_row = df_table[df_table["id"].astype(str) == selected_id].iloc[0]

        st.markdown("### 🔍 상세 정보 (Drill-down)")
        st.json(detail_row.to_dict(), expanded=False)

        score, label, color = compute_risk_score(detail_row)
        st.markdown(f"**위험도:** {color} {label} (score={score})")

        # OSINT Quick Links
        st.markdown("### 🌐 OSINT Quick Links")

        WHOIS_URL = "https://www.whois.com/whois/{domain}"
        HIBP_DOMAIN_URL = "https://haveibeenpwned.com/DomainSearch/{domain}"
        DNSDUMPSTER_URL = "https://dnsdumpster.com/"

        domains_str = detail_row.get("domains", "")
        domains = split_csv_list_cell(domains_str)

        if domains:
            for d in domains:
                st.markdown(f"- **{d}**")
                st.markdown(f"  - [Whois 조회]({WHOIS_URL.format(domain=d)})")
                st.markdown(f"  - [Have I Been Pwned 도메인 검색]({HIBP_DOMAIN_URL.format(domain=d)})")
                st.markdown(f"  - [DNSDumpster 열기]({DNSDUMPSTER_URL})")
        else:
            # “없어서 생성 불가”를 에러처럼 보이지 않게 처리
            st.caption("도메인 정보가 없는 레코드입니다. (OSINT 링크 생략)")

    # ───────────── CSV / JSON 다운로드 ─────────────
    st.markdown("---")
    st.markdown("## ⬇️ 데이터 다운로드 (현재 필터 결과 기준)")

    if df_filtered.empty:
        st.write("다운로드할 데이터가 없습니다.")
    else:
        df_download = df_filtered.copy()

        csv_data = df_download.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="CSV 다운로드",
            data=csv_data,
            file_name="leak_records_filtered.csv",
            mime="text/csv",
        )

        json_data = df_download.to_json(orient="records", force_ascii=False, indent=2).encode("utf-8")
        st.download_button(
            label="JSON 다운로드",
            data=json_data,
            file_name="leak_records_filtered.json",
            mime="application/json",
        )


if __name__ == "__main__":
    main()

# dashboard/app.py

import json
from pathlib import Path
from typing import Tuple, Any
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import re
import math

def normalize_leak_types(value):
    """
    leak_types 셀 하나를 안전하게 [str, str, ...] 리스트로 변환.
    - 리스트, 문자열("[a, b]"), 콤마구분 문자열, 숫자/NaN 모두 처리
    """
    # NaN / None
    if value is None:
        return []

    if isinstance(value, float) and math.isnan(value):
        return []

    # 이미 리스트인 경우
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]

    # 숫자는 카테고리가 아니므로 무시
    if isinstance(value, (int, float)):
        return []

    # 나머지는 전부 문자열로 처리
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return []

    # "['web_defacement', 'data_breach']" 같은 형태 정리
    s = s.strip()
    # 대괄호 제거
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]

    parts = []
    for p in s.split(","):
        p = p.strip()
        # 양쪽 따옴표/작은따옴표 제거
        p = re.sub(r"^['\"]|['\"]$", "", p)
        if p:
            parts.append(p)

    return parts

# ──────────────────────────────────────────────────────────────
# 기본 설정
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Darkweb Leak Intelligence Dashboard",
    layout="wide",
)

# (선택) 간단한 CSS 커스터마이징 – 기존 dashboard.py에서 쓰던 스타일 그대로 옮겨도 됨
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
# 데이터 로딩
# ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_data() -> pd.DataFrame:
    """CSV에서 LeakRecord 데이터를 로드한다."""
    if not CSV_PATH.exists():
        return pd.DataFrame()

    df = pd.read_csv(CSV_PATH)

    # 컬럼이 없을 수도 있으니, 존재할 때만 캐스팅
    for col in ["collected_at", "posted_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # volume 숫자형 컬럼 캐스팅
    if "estimated_volume" in df.columns:
        df["estimated_volume"] = pd.to_numeric(
            df["estimated_volume"], errors="coerce"
        )

    return df


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

    # 데이터 로드
    df = load_data()

    if st.button("데이터 새로고침"):
        # 새 버전(현재 버전)
        if hasattr(st, "rerun"):
            st.rerun()
        # 예전 버전 대비
        elif hasattr(st, "experimental_rerun"):
            st.experimental_rerun()

    if df.empty:
        st.warning("현재 data/leak_records.csv 파일이 없거나, 데이터가 비어 있습니다.")
        return

    # 위험도 컬럼 추가
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

    # 제목 검색
    if q_title and "post_title" in df_filtered.columns:
        df_filtered = df_filtered[
            df_filtered["post_title"]
            .astype(str)
            .str.contains(q_title, case=False, na=False)
        ]

    # 도메인 검색
    if q_domain and "domains" in df_filtered.columns:
        df_filtered = df_filtered[
            df_filtered["domains"]
            .astype(str)
            .str.contains(q_domain, case=False, na=False)
        ]

    # 타겟 서비스 검색
    if q_target and "target_service" in df_filtered.columns:
        df_filtered = df_filtered[
            df_filtered["target_service"]
            .astype(str)
            .str.contains(q_target, case=False, na=False)
        ]

    # source 검색
    if q_source and "source" in df_filtered.columns:
        df_filtered = df_filtered[
            df_filtered["source"]
            .astype(str)
            .str.contains(q_source, case=False, na=False)
        ]

    # any-field 검색
    if q_any:
        text_cols = df_filtered.select_dtypes(include=["object"]).columns
        if len(text_cols) > 0:
            df_tmp = df_filtered.copy()
            df_tmp["_concat"] = (
                df_tmp[text_cols].fillna("").astype(str).agg(" ".join, axis=1)
            )
            df_filtered = df_tmp[
                df_tmp["_concat"].str.contains(q_any, case=False, na=False)
            ].drop(columns=["_concat"])

    # 2) 필터
    st.sidebar.subheader("필터(Filter)")

    # leak_types 필터
    if "leak_types" in df.columns:
        leak_type_values = sorted(
            set(
                t.strip()
                for v in df["leak_types"]
                .dropna()
                .astype(str)
                .str.split(",")
                .sum()
                for t in v.split() if t.strip()
            )
        )
        # 위 comprehension이 너무 복잡하면 아래처럼 단순화해도 된다.
        leak_type_values = sorted(
            set(
                t.strip()
                for v in df["leak_types"]
                .dropna()
                .astype(str)
                for t in v.split(",")
                if t.strip()
            )
        )

        selected_leak_types = st.sidebar.multiselect(
            "Leak Types", leak_type_values
        )
        if selected_leak_types:
            pattern = "|".join(
                [pd.regex.escape(t) for t in selected_leak_types]
            )
            df_filtered = df_filtered[
                df_filtered["leak_types"]
                .astype(str)
                .str.contains(pattern, na=False)
            ]

    # confidence 필터
    if "confidence" in df.columns:
        confidence_values = sorted(
            df["confidence"].dropna().astype(str).unique().tolist()
        )
        selected_confidence = st.sidebar.multiselect(
            "Confidence", confidence_values
        )
        if selected_confidence:
            df_filtered = df_filtered[
                df_filtered["confidence"].astype(str).isin(
                    selected_confidence
                )
            ]

    # 날짜 범위 필터 (collected_at / posted_at)
    date_field = None
    if "collected_at" in df.columns or "posted_at" in df.columns:
        st.sidebar.markdown("---")
        st.sidebar.write("날짜 범위 필터")

        available_date_fields = []
        if "collected_at" in df.columns:
            available_date_fields.append("collected_at")
        if "posted_at" in df.columns:
            available_date_fields.append("posted_at")

        date_field = st.sidebar.selectbox(
            "기준 날짜 컬럼", available_date_fields
        )

        min_date = df[date_field].min()
        max_date = df[date_field].max()
        if pd.isna(min_date) or pd.isna(max_date):
            # 날짜가 없으면 필터 생략
            pass
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

    sort_options = ["정렬 없음"]
    if "posted_at" in df.columns:
        sort_options.append("최신순 (posted_at desc)")
    if "collected_at" in df.columns:
        sort_options.append("최신순 (collected_at desc)")
    if "estimated_volume" in df.columns:
        sort_options.append("volume 큰 순")
    if "source" in df.columns:
        sort_options.append("source 알파벳 순")
    sort_options.append("위험도 높은 순 (risk_score desc)")

    sort_key = st.sidebar.selectbox("정렬 기준", sort_options)

    if sort_key == "최신순 (posted_at desc)" and "posted_at" in df_filtered.columns:
        df_filtered = df_filtered.sort_values(
            "posted_at", ascending=False
        )
    elif (
        sort_key == "최신순 (collected_at desc)"
        and "collected_at" in df_filtered.columns
    ):
        df_filtered = df_filtered.sort_values(
            "collected_at", ascending=False
        )
    elif (
        sort_key == "volume 큰 순"
        and "estimated_volume" in df_filtered.columns
    ):
        df_filtered = df_filtered.sort_values(
            "estimated_volume",
            ascending=False,
            na_position="last",
        )
    elif sort_key == "source 알파벳 순" and "source" in df_filtered.columns:
        df_filtered = df_filtered.sort_values("source", ascending=True)
    elif (
        sort_key == "위험도 높은 순 (risk_score desc)"
        and "risk_score" in df_filtered.columns
    ):
        df_filtered = df_filtered.sort_values(
            "risk_score", ascending=False
        )

    # ───────────── 상단 KPI 영역 ─────────────
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("전체 레코드 수", len(df))
    with col2:
        st.metric("현재 필터된 레코드 수", len(df_filtered))
    with col3:
        if "source" in df.columns:
            st.metric("소스(채널) 개수", df["source"].nunique())

    # ───────────── 그래프 시각화 ─────────────
    st.markdown("## 📈 통계 / 시각화")

    if df_filtered.empty:
        st.info("현재 조건에 해당하는 레코드가 없습니다.")
    else:
        col_g1, col_g2 = st.columns(2)

        # 날짜별 누출 건수 추이
        with col_g1:
            if "posted_at" in df_filtered.columns or "collected_at" in df_filtered.columns:
                date_field_for_chart = (
                    date_field
                    if date_field in ["posted_at", "collected_at"]
                    else (
                        "posted_at"
                        if "posted_at" in df_filtered.columns
                        else "collected_at"
                    )
                )
                df_time = df_filtered.copy()
                df_time[date_field_for_chart] = pd.to_datetime(
                    df_time[date_field_for_chart], errors="coerce"
                )
                df_time = df_time.dropna(subset=[date_field_for_chart])
                if not df_time.empty:
                    daily_counts = (
                        df_time.groupby(
                            df_time[date_field_for_chart].dt.date
                        )
                        .size()
                        .reset_index(name="count")
                    )
                    daily_counts.set_index(date_field_for_chart, inplace=True)

                    st.subheader("날짜별 누출 건수 추이")
                    st.line_chart(daily_counts["count"])
                else:
                    st.write("날짜 정보가 없어 트렌드 차트를 표시할 수 없습니다.")

        # 채널별 누출 비중 (bar chart)
        with col_g2:
            if "source" in df_filtered.columns:
                st.subheader("채널별 누출 건수 (source 기준)")
                channel_counts = (
                    df_filtered["source"]
                    .astype(str)
                    .value_counts()
                    .reset_index()
                )
                channel_counts.columns = ["source", "count"]
                st.bar_chart(
                    channel_counts.set_index("source")["count"]
                )

        # Leak Types 비율 (pie chart)
        st.subheader("Leak Types 비율")
        if "leak_types" in df_filtered.columns:
            all_types = []
            for v in df_filtered["leak_types"]:
                all_types.extend(normalize_leak_types(v))

            if all_types:
                type_counts = pd.Series(all_types).value_counts()
                fig, ax = plt.subplots()
                ax.pie(
                    type_counts.values,
                    labels=type_counts.index,
                    autopct="%1.1f%%",
                )
                ax.axis("equal")
                st.pyplot(fig)
            else:
                st.write("Leak Types 데이터가 없습니다.")
        else:
            st.write("leak_types 컬럼이 없습니다.")
            
        st.subheader("소스별 × 카테고리별 건수")
        if ("source" in df_filtered.columns) and ("leak_types" in df_filtered.columns):
            rows = []

            for _, row in df_filtered[["source", "leak_types"]].iterrows():
                src = str(row["source"])
                types = normalize_leak_types(row["leak_types"])
                for t in types:
                    rows.append({"source": src, "leak_type": t})

            if rows:
                pivot_df = (
                    pd.DataFrame(rows)
                    .pivot_table(
                        index="source",
                        columns="leak_type",
                        aggfunc="size",
                        fill_value=0,
                    )
                    .sort_index()
                )
                st.dataframe(pivot_df)
                st.caption("행: 소스(채널), 열: 카테고리(leak_type), 값: 레코드 수")
            else:
                st.write("소스 × 카테고리 조합 데이터가 없습니다.")
        else:
            st.write("source / leak_types 컬럼이 없어 피벗 테이블을 만들 수 없습니다.")

    # ───────────── 레코드 테이블 + 상세 보기 ─────────────
    st.markdown("## 📄 Leak Records")

    # 리스트 테이블에 보여줄 기본 컬럼
    columns_for_table = []
    for col in [
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
    ]:
        if col in df_filtered.columns:
            columns_for_table.append(col)

    if not df_filtered.empty:
        st.dataframe(
            df_filtered[columns_for_table],
            use_container_width=True,
            hide_index=True,
        )

    # 상세 보기용 key 결정 (id 컬럼이 없으면 index 사용)
    if "id" in df_filtered.columns:
        record_ids = df_filtered["id"].astype(str).tolist()
        id_label = "id"
    else:
        df_filtered = df_filtered.reset_index().rename(
            columns={"index": "_idx"}
        )
        record_ids = df_filtered["_idx"].astype(str).tolist()
        id_label = "index"

    if record_ids:
        selected_id = st.selectbox(
            f"상세 보기할 레코드 선택 ({id_label})",
            record_ids,
        )

        # 선택된 레코드 추출
        if id_label == "id":
            detail_row = df_filtered[df_filtered["id"].astype(str) == selected_id].iloc[0]
        else:
            detail_row = df_filtered[
                df_filtered["_idx"].astype(str) == selected_id
            ].iloc[0]

        st.markdown("### 🔍 상세 정보 (Drill-down)")
        st.json(detail_row.to_dict(), expanded=False)

        # 위험도 표시
        score, label, color = compute_risk_score(detail_row)
        st.markdown(
            f"**위험도:** {color} {label} (score={score})"
        )

        # ───── OSINT Quick Links ─────
        st.markdown("### 🌐 OSINT Quick Links")

        WHOIS_URL = "https://www.whois.com/whois/{domain}"
        HIBP_DOMAIN_URL = "https://haveibeenpwned.com/DomainSearch/{domain}"
        DNSDUMPSTER_URL = "https://dnsdumpster.com/"

        domains_str = detail_row.get("domains", "")
        domains = [
            d.strip()
            for d in str(domains_str).split(",")
            if d.strip()
        ]

        if domains:
            for d in domains:
                st.markdown(f"- **{d}**")
                st.markdown(
                    f"  - [Whois 조회]({WHOIS_URL.format(domain=d)})"
                )
                st.markdown(
                    f"  - [Have I Been Pwned 도메인 검색]({HIBP_DOMAIN_URL.format(domain=d)})"
                )
                st.markdown(
                    f"  - [DNSDumpster 열기]({DNSDUMPSTER_URL})"
                )
        else:
            st.write("domains 정보가 없어 OSINT 링크를 생성할 수 없습니다.")

    # ───────────── CSV / JSON 다운로드 ─────────────
    st.markdown("---")
    st.markdown("## ⬇️ 데이터 다운로드 (현재 필터 결과 기준)")

    if df_filtered.empty:
        st.write("다운로드할 데이터가 없습니다.")
    else:
        # index 컬럼 제거
        df_download = df_filtered.drop(columns=[c for c in df_filtered.columns if c == "_idx"], errors="ignore")

        csv_data = df_download.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="CSV 다운로드",
            data=csv_data,
            file_name="leak_records_filtered.csv",
            mime="text/csv",
        )

        json_data = df_download.to_json(
            orient="records", force_ascii=False, indent=2
        ).encode("utf-8")
        st.download_button(
            label="JSON 다운로드",
            data=json_data,
            file_name="leak_records_filtered.json",
            mime="application/json",
        )


# ──────────────────────────────────────────────────────────────
# 엔트리 포인트
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()

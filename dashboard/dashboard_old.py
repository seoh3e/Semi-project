import json
from pathlib import Path

import pandas as pd
import streamlit as st

# ---- 기본 UI 세팅 & 간단 CSS ----
st.set_page_config(
    page_title="Darkweb Leak Intelligence Dashboard",
    layout="wide"
)

# 약간의 여백 / 폰트 크기 조정
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
        color: #bbbbbb;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📊 Darkweb Leak Intelligence Dashboard")
st.markdown("텔레그램 기반 다크웹 유출 정보 자동 수집 · 파싱 시스템 대시보드")

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "leak_records.csv"


@st.cache_data
def load_data():
    try:
        df = pd.read_csv(DATA_PATH)
        # 날짜 컬럼이 있으면 datetime으로 변환
        for col in ["collected_at", "posted_at"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        return df
    except Exception as e:
        st.error(f"CSV 파일을 열 수 없습니다: {e}")
        return pd.DataFrame()


# ---- (준)실시간 새로고침: 버튼 + 선택적 자동 리프레시 ----
st.sidebar.header("🔄 데이터 새로고침")

manual_refresh = st.sidebar.button("지금 새로고침")

# 선택: streamlit-autorefresh 설치 시 주기적 리프레시 지원
# pip install streamlit-autorefresh
AUTO_REFRESH_ENABLED = False
try:
    from streamlit_autorefresh import st_autorefresh  # type: ignore

    AUTO_REFRESH_ENABLED = True
except Exception:
    AUTO_REFRESH_ENABLED = False

if AUTO_REFRESH_ENABLED:
    interval_seconds = st.sidebar.slider(
        "자동 새로고침 주기(초)",
        min_value=0,
        max_value=300,
        value=0,
        step=10,
        help="0이면 자동 새로고침 없음",
    )
    if interval_seconds > 0:
        st.sidebar.caption("💡 CSV가 갱신되면 지정한 주기마다 자동으로 반영됩니다.")
        st_autorefresh(interval=interval_seconds * 1000, key="auto-refresh")

if manual_refresh:
    st.experimental_rerun()

df = load_data()
st.write(f"현재 수집된 레코드 수: **{len(df)}**")

if df.empty:
    st.info("data/leak_records.csv 파일이 없거나 데이터가 없습니다.")
    st.stop()

# =========================================
# 1️⃣ 검색(Search)
# =========================================

st.sidebar.header("🔍 검색 / 필터")

search_query = st.sidebar.text_input(
    "키워드 검색 (제목, 타깃 서비스, 도메인 등)",
    value="",
    placeholder="예: vpn, example.com, KR, university ...",
)

filtered = df.copy()

if search_query.strip():
    q = search_query.strip().lower()
    search_cols = [
        col
        for col in [
            "post_title",
            "target_service",
            "domains",
            "source",
            "leak_types",
            "country",
            "threat_claim",
        ]
        if col in filtered.columns
    ]

    if search_cols:
        mask = False
        for col in search_cols:
            mask = mask | filtered[col].astype(str).str.lower().str.contains(
                q, na=False
            )
        filtered = filtered[mask]

# =========================================
# 2️⃣ 필터(Filter)
# =========================================

# Source 필터
if "source" in df.columns:
    source_options = sorted(df["source"].dropna().unique())
    selected_sources = st.sidebar.multiselect(
        "Source(채널/포럼) 선택",
        options=source_options,
        default=source_options,
    )
    if selected_sources:
        filtered = filtered[filtered["source"].isin(selected_sources)]

# Confidence 필터
if "confidence" in df.columns:
    conf_options = sorted(df["confidence"].fillna("unknown").unique())
    selected_conf = st.sidebar.multiselect(
        "Confidence 선택",
        options=conf_options,
        default=conf_options,
    )
    if selected_conf:
        filtered = filtered[filtered["confidence"].isin(selected_conf)]

# Leak types 필터
if "leak_types" in df.columns:
    leak_type_all = set()
    for v in df["leak_types"].dropna().astype(str):
        for t in [x.strip() for x in v.split(",")]:
            if t:
                leak_type_all.add(t)
    leak_type_all = sorted(list(leak_type_all))

    selected_leak_types = st.sidebar.multiselect(
        "Leak Types 선택",
        options=leak_type_all,
        default=leak_type_all,
    )
    if selected_leak_types:
        mask = False
        for t in selected_leak_types:
            mask = mask | filtered["leak_types"].astype(str).str.contains(t, na=False)
        filtered = filtered[mask]

# 날짜 필터
if "collected_at" in df.columns:
    min_date = pd.to_datetime(df["collected_at"]).min()
    max_date = pd.to_datetime(df["collected_at"]).max()

    date_range = st.sidebar.date_input(
        "수집일 범위(collected_at)",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered = filtered[
            (filtered["collected_at"] >= pd.to_datetime(start_date))
            & (filtered["collected_at"] <= pd.to_datetime(end_date))
        ]

# =========================================
# 3️⃣ 정렬(Sort)
# =========================================

sort_options = [
    "최신 수집일 내림차순",
    "수집일 오름차순",
    "유출 규모(estimated_volume) 내림차순",
    "유출 규모 오름차순",
]

sort_choice = st.sidebar.selectbox("정렬 기준", sort_options)

if sort_choice == "최신 수집일 내림차순" and "collected_at" in filtered.columns:
    filtered = filtered.sort_values("collected_at", ascending=False)
elif sort_choice == "수집일 오름차순" and "collected_at" in filtered.columns:
    filtered = filtered.sort_values("collected_at", ascending=True)
elif (
    sort_choice == "유출 규모(estimated_volume) 내림차순"
    and "estimated_volume" in filtered.columns
):
    filtered = filtered.sort_values(
        "estimated_volume", ascending=False, na_position="last"
    )
elif (
    sort_choice == "유출 규모 오름차순"
    and "estimated_volume" in filtered.columns
):
    filtered = filtered.sort_values(
        "estimated_volume", ascending=True, na_position="last"
    )

st.markdown(f"### 🔎 필터 적용 후 레코드 수: **{len(filtered)}**")

# =========================================
# 4️⃣ 그래프(Charts)
# =========================================

st.divider()
st.subheader("📈 간단 통계 시각화")

col_chart1, col_chart2 = st.columns(2)

if "confidence" in filtered.columns:
    with col_chart1:
        st.markdown("#### Confidence 분포")
        conf_counts = filtered["confidence"].fillna("unknown").value_counts()
        st.bar_chart(conf_counts)

if "source" in filtered.columns:
    with col_chart2:
        st.markdown("#### Source별 건수")
        source_counts = filtered["source"].fillna("Unknown").value_counts()
        st.bar_chart(source_counts)

if "collected_at" in filtered.columns:
    st.markdown("#### 📆 수집일 기준 건수 추이")
    date_counts = (
        filtered.dropna(subset=["collected_at"])
        .groupby(filtered["collected_at"].dt.date)
        .size()
        .rename("count")
    )
    st.line_chart(date_counts)

# =========================================
# 5️⃣ 리스트 + 상세 보기 + OSINT 링크
# =========================================

st.divider()
st.subheader("📄 유출 데이터 리스트")

main_cols = [
    "collected_at",
    "source",
    "post_title",
    "target_service",
    "domains",
    "estimated_volume",
    "leak_types",
    "confidence",
]
main_cols = [c for c in main_cols if c in filtered.columns]

st.dataframe(
    filtered[main_cols],
    use_container_width=True,
    height=350,
)

st.subheader("🔎 선택한 레코드 상세 보기")

if len(filtered) > 0:
    idx = st.number_input(
        "상세보기할 index 선택",
        min_value=0,
        max_value=len(filtered) - 1,
        step=1,
        value=0,
    )
    record = filtered.iloc[int(idx)]

    st.markdown("#### 주요 정보")
    info_cols = [
        "collected_at",
        "source",
        "post_title",
        "post_id",
        "author",
        "posted_at",
        "target_service",
        "domains",
        "leak_types",
        "estimated_volume",
        "file_formats",
        "country",
        "confidence",
    ]
    for c in info_cols:
        if c in record.index:
            st.write(f"**{c}**: {record[c]}")

    st.markdown("#### Threat / Deal / OSINT Seeds (원문)")

    for c in ["threat_claim", "deal_terms", "osint_seeds"]:
        if c in record.index and pd.notna(record[c]):
            st.write(f"**{c}**")
            st.code(str(record[c]))

    # ---- 🌐 OSINT Quick Links ----
    st.markdown("### 🌐 OSINT Quick Links")

    # 도메인 기반 링크
    domains_str = str(record.get("domains", "") or "")
    domain_list = [
        d.strip() for d in domains_str.replace(";", ",").split(",") if d.strip()
    ]

    if domain_list:
        st.markdown("**도메인 기반 분석 링크**")
        for d in domain_list:
            st.markdown(
                f"- `{d}` → "
                f"[Whois](https://who.is/whois/{d})  |  "
                f"[VirusTotal](https://www.virustotal.com/gui/domain/{d})  |  "
                f"[URLScan](https://urlscan.io/domain/{d})"
            )
    else:
        st.caption("도메인 정보가 없어 도메인 기반 OSINT 링크를 생성할 수 없습니다.")

    # osint_seeds가 JSON/딕셔너리라면 가독성 있게 파싱
    raw_seeds = record.get("osint_seeds", None)
    if pd.notna(raw_seeds):
        try:
            # 문자열인 경우 JSON으로 파싱 시도
            if isinstance(raw_seeds, str):
                seeds_obj = json.loads(raw_seeds)
            else:
                seeds_obj = raw_seeds

            if isinstance(seeds_obj, dict):
                st.markdown("**추가 OSINT Seed 필드**")
                st.json(seeds_obj)
        except Exception:
            # 그냥 위에서 code로 보여준 걸로 충분
            pass

else:
    st.info("필터 결과가 없습니다.")

# =========================================
# 6️⃣ 다운로드 버튼
# =========================================

st.divider()
st.subheader("⬇️ 데이터 다운로드")

csv_bytes = filtered.to_csv(index=False).encode("utf-8")
st.download_button(
    label="필터된 데이터 CSV 다운로드",
    data=csv_bytes,
    file_name="leak_records_filtered.csv",
    mime="text/csv",
)

st.markdown(
    '<p class="small-text">※ CSV는 현재 검색/필터/정렬이 적용된 상태 그대로 다운로드됩니다.</p>',
    unsafe_allow_html=True,
)

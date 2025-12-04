from pyrogram import Client
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Dict


# ==========================================
# LeakRecord 클래스
# ==========================================
@dataclass
class LeakRecord:
    collected_at: date
    source: str
    post_title: str
    post_id: str
    author: Optional[str]
    posted_at: Optional[date]

    leak_types: List[str]
    estimated_volume: Optional[int]
    file_formats: List[str]

    target_service: Optional[str]
    domains: List[str]
    country: Optional[str]

    threat_claim: Optional[str]
    deal_terms: Optional[str]
    confidence: str

    screenshot_refs: List[str] = field(default_factory=list)
    osint_seeds: Dict = field(default_factory=dict)


# ==========================================
# Pyrogram 설정
# ==========================================
api_id = 33634099
api_hash = "f313b1b911e2abe7044049359a8ddee9"
channel = "@hackmanac_cybernews"

app = Client("session", api_id=api_id, api_hash=api_hash)
records: List[LeakRecord] = []


# ==========================================
# 메시지 수집 및 파싱
# ==========================================
with app:
    for message in app.get_chat_history(channel, limit=1):

        text = message.text or message.caption
        if not text:
            continue

        # Alert 메시지만 처리
        if "Alert" not in text.split("\n", 1)[0]:
            continue

        lines = text.split("\n")

        # -----------------------------
        # 국가/서비스 분리 (앞: 국가, 뒤: 서비스)
        # -----------------------------
        country_line = lines[2] if len(lines) > 2 else ""
        if "-" in country_line:
            country_val, target_service_val = map(str.strip, country_line.split("-", 1))
        else:
            country_val = ""
            target_service_val = country_line.strip()

        # -----------------------------
        # extra_lines = Sector: 전까지
        # -----------------------------
        extra_lines = []
        for i in range(3, len(lines)):
            if lines[i].startswith("Sector:"):
                break
            extra_lines.append(lines[i])

        # 제목 추출 = 첫 문장의 첫 온점 전
        post_title_val = extra_lines[1].split(". ", 1)[0] if extra_lines else ""

        # -----------------------------
        # 키워드 파싱
        # -----------------------------
        keywords = ["Sector:", "Threat class:", "Status:", "Observed:", "Source:"]
        keyword_values = {}

        for line in lines:
            for key in keywords:
                if line.startswith(key):
                    keyword_values[key[:-1]] = line.split(": ", 1)[1]

        # -----------------------------
        # posted_at 처리
        # -----------------------------
        observed_str = keyword_values.get("Observed")
        if observed_str:
            try:
                posted_at_val = date.fromisoformat(observed_str)
            except ValueError:
                posted_at_val = message.date.date() if message.date else None
        else:
            posted_at_val = message.date.date() if message.date else None

        # 메시지 ID
        post_id_val = str(message.id) if hasattr(message, "id") else ""

        # 작성자
        author_val = getattr(message.from_user, "username", None) if message.from_user else None

        # ==========================================
        # LeakRecord 생성
        # ==========================================
        record = LeakRecord(
            collected_at=date.today(),
            source=channel,
            post_title=post_title_val,
            post_id=post_id_val,
            author=author_val,
            posted_at=posted_at_val,

            leak_types=[],
            estimated_volume=None,
            file_formats=[],

            target_service=target_service_val,
            domains=[],
            country=country_val,

            threat_claim=None,
            deal_terms=None,
            confidence=""
        )

        # 키워드(메타데이터)를 별도 저장 (LeakRecord에는 넣지 않음)
        record._parsed_keywords = {
            "Sector": keyword_values.get("Sector", ""),
            "Threat Class": keyword_values.get("Threat class", ""),
            "Status": keyword_values.get("Status", ""),
            "Source": keyword_values.get("Source", "")
        }

        records.append(record)


# ==========================================
# 전체 출력
# ==========================================
for idx, r in enumerate(records, 1):
    print("=" * 60)
    print(f"LeakRecord #{idx}")
    print("-" * 60)

    print(f"Collected at   : {r.collected_at}")
    print(f"Source (Record): {r.source}")  # LeakRecord.source = 채널명
    print(f"Post Title     : {r.post_title}")
    print(f"Post ID        : {r.post_id}")
    print(f"Author         : {r.author}")
    print(f"Posted at      : {r.posted_at}")
    print()

    print(f"Target Service : {r.target_service}")
    print(f"Domains        : {r.domains}")
    print(f"Country        : {r.country}")
    print()

    print("[Parsed Metadata]")
    print(f"Sector        : {r._parsed_keywords.get('Sector')}")
    print(f"Threat Class  : {r._parsed_keywords.get('Threat Class')}")
    print(f"Status        : {r._parsed_keywords.get('Status')}")
    print(f"Source        : {r._parsed_keywords.get('Source')}")
    print()

    print(f"Leak Types     : {r.leak_types}")
    print(f"Estimated Vol. : {r.estimated_volume}")
    print(f"File Formats   : {r.file_formats}")
    print()

    print(f"Threat Claim   : {r.threat_claim}")
    print(f"Deal Terms     : {r.deal_terms}")
    print(f"Confidence     : {r.confidence}")
    print()

    print(f"Screenshots    : {r.screenshot_refs}")
    print(f"OSINT Seeds    : {r.osint_seeds}")
    print("=" * 60)
    print()

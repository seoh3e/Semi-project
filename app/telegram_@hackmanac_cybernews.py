from pyrogram import Client
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional, Dict
import os
import re
import whois

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
    domains: str  # 문자열로 저장
    country: str  # ISO 코드로 저장

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
# 다운로드 폴더
# ==========================================
download_folder = "screenshots"
os.makedirs(download_folder, exist_ok=True)

# ==========================================
# 국기 → ISO 코드 변환
# ==========================================
def emoji_to_iso_codes(text: str) -> str:
    """
    - text에 포함된 국기 이모지를 ISO 3166-1 alpha-2 코드로 변환
    - 여러 개일 경우 쉼표로 연결
    - 국기 없는 경우 빈 문자열 반환
    """
    flags = re.findall(r'[\U0001F1E6-\U0001F1FF]{2}', text)
    codes = []
    for f in flags:
        code = ''.join([chr(ord(c) - 127397) for c in f])
        codes.append(code)
    return ", ".join(codes)

# ==========================================
# WHOIS 조회
# ==========================================
def whois_domains_from_service(service_name: str) -> List[str]:
    candidate_domain = service_name.replace(" ", "").lower() + ".com"
    try:
        w = whois.whois(candidate_domain)
        if w.domain_name:
            # 문자열로 반환, 리스트 형태일 경우 처리
            if isinstance(w.domain_name, list):
                return w.domain_name
            return [w.domain_name]
        return []
    except Exception:
        return []

# ==========================================
# 메시지 수집 및 파싱
# ==========================================
with app:
    for message in app.get_chat_history(channel, limit=100):
        text = message.text or message.caption
        if not text:
            continue

        if "Alert" not in text.split("\n", 1)[0]:
            continue

        lines = text.split("\n")

        # 국가/서비스 분리
        country_line = lines[2] if len(lines) > 2 else ""
        if "-" in country_line:
            country_part, target_service_val = map(str.strip, country_line.split("-", 1))
        else:
            country_part = country_line.strip()
            target_service_val = ""

        # Country → ISO 코드
        country_val = emoji_to_iso_codes(country_part)

        # Sector 이전까지 extra_lines 추출
        extra_lines = []
        for i in range(3, len(lines)):
            if lines[i].startswith("Sector:"):
                break
            extra_lines.append(lines[i])

        post_title_val = extra_lines[1].split(". ", 1)[0] if len(extra_lines) > 1 else ""

        # 키워드 파싱
        keywords = ["Sector:", "Threat class:", "Status:", "Observed:", "Source:"]
        keyword_values = {}
        for line in lines:
            for key in keywords:
                if line.startswith(key):
                    keyword_values[key[:-1]] = line.split(": ", 1)[1]

        # Source만 있는 경우 스킵
        other_keys = ["Sector", "Threat class", "Status", "Observed"]
        if not any(keyword_values.get(k) for k in other_keys):
            continue

        # posted_at 처리
        observed_str = keyword_values.get("Observed")
        posted_at_val = None
        if observed_str:
            try:
                dt = datetime.strptime(observed_str, "%b %d, %Y")
                posted_at_val = dt.date()
            except ValueError:
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

        # 사진/문서 다운로드 처리
        screenshot_refs_val = []
        if message.photo:
            file_path = os.path.join(download_folder, f"{post_id_val}_photo.jpg")
            message.download(file_path)
            screenshot_refs_val.append(file_path)
        if message.document:
            file_name = message.document.file_name or f"{post_id_val}_document"
            file_path = os.path.join(download_folder, file_name)
            message.download(file_path)
            screenshot_refs_val.append(file_path)
        if message.media_group_id:
            media_group = app.get_media_group(channel, message.message_id)
            for media_msg in media_group:
                if media_msg.photo:
                    file_path = os.path.join(download_folder, f"{media_msg.message_id}_photo.jpg")
                    media_msg.download(file_path)
                    screenshot_refs_val.append(file_path)
                if media_msg.document:
                    file_name = media_msg.document.file_name or f"{media_msg.message_id}_document"
                    file_path = os.path.join(download_folder, file_name)
                    media_msg.download(file_path)
                    screenshot_refs_val.append(file_path)

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
            domains="",  # 문자열로 처리
            country=country_val,
            threat_claim=None,
            deal_terms=None,
            confidence="",
            screenshot_refs=screenshot_refs_val
        )

        # 키워드 메타데이터 저장
        record._parsed_keywords = {
            "Sector": keyword_values.get("Sector", ""),
            "Threat Class": keyword_values.get("Threat class", ""),
            "Status": keyword_values.get("Status", ""),
            "Source": keyword_values.get("Source", "")
        }

        # target_service_val 기반 WHOIS 도메인 조회 → 문자열로 저장
        if target_service_val:
            whois_domains = whois_domains_from_service(target_service_val)
            record.domains = ", ".join(whois_domains) if whois_domains else ""

        records.append(record)

# ==========================================
# 전체 출력
# ==========================================
for idx, r in enumerate(records, 1):
    print("=" * 60)
    print(f"LeakRecord #{idx}")
    print("-" * 60)
    print(f"Collected at   : {r.collected_at}")
    print(f"Source (Record): {r.source}")
    print(f"Post Title     : {r.post_title}")
    print(f"Post ID        : {r.post_id}")
    print(f"Author         : {r.author}")
    print(f"Posted at      : {r.posted_at}")
    print()
    print(f"Target Service : {r.target_service}")
    print(f"Domains        : {r.domains}")
    print(f"Country        : {r.country}")  # ISO 코드로 출력
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

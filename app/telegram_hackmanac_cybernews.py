# app/telegram_hackmanac_cybernews.py

import re
from datetime import date, datetime
from typing import Optional, List

from .models import IntermediateEvent, LeakRecord


# ─────────────────────────────────────────────
# 1) raw_text → IntermediateEvent
# ─────────────────────────────────────────────


def parse_hackmanac_cybernews(
    raw_text: str,
    message_id: Optional[int] = None,
    message_url: Optional[str] = None,
) -> IntermediateEvent:
    """
    hackmanac_cybernews 채널 메시지 파서.
    텍스트에서 피해자, 공격그룹, 관측 날짜, URL 등을 뽑아서 IntermediateEvent로 반환.
    """

    lines = raw_text.splitlines()

    victim: Optional[str] = None
    group: Optional[str] = None
    published_date_text: Optional[str] = None
    urls: List[str] = []
    tags: List[str] = []

    for idx, line in enumerate(lines):
        line = line.strip()

        # 날짜 정보 (예: "Observed: Dec 5, 2025")
        if "Observed:" in line:
            parts = line.split("Observed:", 1)
            if len(parts) > 1:
                published_date_text = parts[1].strip()

        # 그룹명 (예: "Nova hacking group claims to have breached ...")
        if "hacking group" in line:
            parts = line.split("hacking group", 1)
            if len(parts) > 0:
                group = parts[0].strip()

        # 피해자 (예: "🇿🇲Zambia - National Health Insurance Scheme (NHIS)")
        # 위 예시 기준으로, 국기 + 국가명 + " - " + 기관명 구조라서,
        # " - " 기준 오른쪽을 피해자/서비스명으로 사용
        if idx == 2 and " - " in line:
            parts = line.split(" - ", 1)
            if len(parts) > 1:
                victim = parts[1].strip()

        # URL (예: "Source: https://...")
        if "Source:" in line:
            parts = line.split("Source:", 1)
            if len(parts) > 1:
                url = parts[1].strip()
                if url:
                    urls.append(url)

    return IntermediateEvent(
        source_channel="@hackmanac_cybernews",
        raw_text=raw_text,
        message_id=message_id,
        message_url=message_url,
        group_name=group,
        victim_name=victim,
        published_at_text=published_date_text,
        urls=urls,
        tags=tags,
    )


# ─────────────────────────────────────────────
# 2) IntermediateEvent → LeakRecord 변환기
# ─────────────────────────────────────────────


def intermediate_to_hackmanac_cybernews_leakrecord(
    event: IntermediateEvent,
) -> LeakRecord:
    """
    파싱된 IntermediateEvent → LeakRecord 표준 구조 변환.
    - published_at_text가 없거나 파싱 실패하면 오늘 날짜(date.today()) 사용.
    - 국기 이모지를 국가코드(예: 🇿🇲 → ZM)로 변환 시도, 실패하면 None.
    - 본문에서 exfiltrated 문장을 찾아 유출량/유형 추출.
    - Status: 값에 따라 confidence 매핑.
    """

    status_to_confidence = {
        "Pending verification": "medium",
        "Confirmed": "high",
    }

    lines = event.raw_text.splitlines()
    country: Optional[str] = None
    estimated_volume: Optional[str] = None
    leak_types: List[str] = []
    status: Optional[str] = None

    # 두 번째 라인(예: "🇿🇲Zambia - National Health Insurance Scheme (NHIS)")
    # 에서 맨 앞의 국기 이모지를 ISO2 코드로 변환 시도
    if len(lines) >= 3:
        line = lines[2].strip()
        if " - " in line and line:
            flag = line[:2]  # 국기 이모지 한 쌍 (예: "🇿🇲")
            try:
                # Regional Indicator Symbol 'A' (0x1F1E6)를 'A' ~ 'Z'로 매핑
                OFFSET = 0x1F1E6
                country = "".join(chr(ord(c) - OFFSET + ord("A")) for c in flag)
            except Exception:
                country = None

    # 본문에서 유출량/유형, Status 추출
    for line in lines:
        line = line.strip()

        # 예: "Allegedly, the attackers exfiltrated 50GB of data, including personal information."
        if " exfiltrated " in line:
            phrase = line.split(" exfiltrated ", 1)[1].rstrip(".")
            if " of " in phrase:
                estimated_volume = phrase.split(" of ", 1)[0].strip()
                if ", including " in phrase:
                    leak_types_part = phrase.split(", including ", 1)[1].rstrip(".")
                    leak_types.append(leak_types_part.strip())
            else:
                leak_types.append(phrase.strip())

        # 예: "Status: Pending verification"
        if line.startswith("Status:"):
            status = line.split("Status:", 1)[1].strip()

    # 관측 날짜 파싱
    if getattr(event, "published_at_text", None):
        try:
            posted_at = datetime.strptime(
                event.published_at_text, "%b %d, %Y"
            ).date()
        except Exception:
            posted_at = date.today()
    else:
        posted_at = date.today()

    # 타이틀: "그룹 → 피해자" 형태로 구성
    title = f"{event.group_name or ''} → {event.victim_name or ''}".strip()
    if not title or title == "→":
        title = (event.victim_name or event.group_name or "").strip()

    # Status 기반 confidence 설정 (없으면 기본 medium)
    confidence = "medium"
    if status:
        confidence = status_to_confidence.get(status, "medium")

    return LeakRecord(
        collected_at=date.today(),
        source=event.source_channel,
        post_title=title,
        post_id=str(event.message_id) if event.message_id is not None else "",
        author=None,
        posted_at=posted_at,
        leak_types=leak_types,
        estimated_volume=estimated_volume,
        file_formats=[],
        target_service=event.victim_name,
        domains=[],
        country=country,
        threat_claim=event.group_name,
        deal_terms=None,
        confidence=confidence,
        screenshot_refs=[],
        osint_seeds={"urls": event.urls or []},
    )

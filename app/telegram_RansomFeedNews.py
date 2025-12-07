# app/telegram_ransomfeednews.py

import re
from datetime import date
from typing import Optional, List
from app.models import IntermediateEvent, LeakRecord


#─────────────────────────────────────────────
# 1) raw_text → IntermediateEvent
#─────────────────────────────────────────────

def parse_RansomFeedNews(raw_text: str, message_id=None, message_url=None) -> IntermediateEvent:
    """
    RansomFeedNews 채널 메시지 파서.
    """

    lines = raw_text.splitlines()

    victim = None
    group = None
    published_date_text = None
    urls: List[str] = []

    # 기본 포맷:
    # ID: 27651
    # ⚠ Thu, 04 Dec 2025 09:25:47 CET
    # 🐺 qilin
    # 🎯 Yellow Cab of Columbus, USA
    # 🔗 http://www.ransomfeed.it/index.php?page=post_details&id_post=27651

    for line in lines:
        # 날짜 정보
        if "CET" in line or "UTC" in line:
            published_date_text = line.strip()

        # 그룹명
        if "🐺" in line or "🎭" in line or "👿" in line or "😈" in line or "☠" in line:
            parts = line.split()
            if len(parts) > 1:
                group = " ".join(parts[1:]).strip()

        # 피해자
        if "🎯" in line:
            parts = line.split("🎯")
            if len(parts) > 1:
                victim = parts[1].strip()

        # URL
        if "http" in line:
            urls.append(line.strip())

    return IntermediateEvent(
        source_channel="RansomFeedNews",
        raw_text=raw_text,
        message_id=message_id,
        message_url=message_url,
        group_name=group,
        victim_name=victim,
        published_at_text=published_date_text,
        urls=urls,
        tags=[],
    )


#─────────────────────────────────────────────
# 2) IntermediateEvent → LeakRecord 변환기
#─────────────────────────────────────────────

def intermediate_to_leakrecord(event: IntermediateEvent) -> LeakRecord:
    """
    파싱된 IntermediateEvent → LeakRecord 표준 구조 변환
    """

    return LeakRecord(
        collected_at=date.today(),
        source=event.source_channel,
        post_title=f"{event.group_name or ''} → {event.victim_name or ''}",
        post_id=str(event.message_id) if event.message_id else "",
        author=None,
        posted_at=None,

        leak_types=[],
        estimated_volume=None,
        file_formats=[],

        target_service=event.victim_name,
        domains=[],
        country=None,

        threat_claim=event.group_name,
        deal_terms=None,
        confidence="medium",

        screenshot_refs=[],
        osint_seeds={"urls": event.urls},
    )

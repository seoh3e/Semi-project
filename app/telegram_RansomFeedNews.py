# app/telegram_RansomFeedNews.py

import re
from datetime import date, datetime
from typing import Optional, List
from .models import IntermediateEvent, LeakRecord


# ─────────────────────────────────────────────
# 1) raw_text → IntermediateEvent
# ─────────────────────────────────────────────


def parse_RansomFeedNews(
    raw_text: str, message_id=None, message_url=None
) -> IntermediateEvent:
    """
    RansomFeedNews 채널 메시지 파서.
    """

    lines = raw_text.splitlines()

    published_date_text = None
    group = None
    victim = None
    urls: List[str] = []

    # 기본 포맷:
    # ID: 27781
    # ⚠️ Sun, 07 Dec 2025 14:42:25 CET
    # 🥷 sinobi
    # 🎯 Quality Companies, USA
    # 🔗 http://www.ransomfeed.it/index.php?page=post_details&id_post=27781

    published_date_text = datetime.strptime(lines[1][3:-5], "%a, %d %b %Y %H:%M:%S").date()

    group = lines[2][2:-1]

    victim = lines[3][2:-1]

    urls.append(lines[4][2:])

    return IntermediateEvent(
        source_channel="@RansomFeedNews",
        raw_text=raw_text,
        message_id=message_id,
        message_url=message_url,
        group_name=group,
        victim_name=victim,
        published_at_text=published_date_text,
        urls=urls,
        tags=[],
    )


# ─────────────────────────────────────────────
# 2) IntermediateEvent → LeakRecord 변환기
# ─────────────────────────────────────────────


def intermediate_to_RansomFeedNews_leakrecord(event: IntermediateEvent) -> LeakRecord:
    """
    파싱된 IntermediateEvent → LeakRecord 표준 구조 변환
    """

    return LeakRecord(
        collected_at=date.today(),
        source=event.source_channel,
        post_title=f"{event.group_name or ''} → {event.victim_name or ''}",
        post_id=str(event.message_id) if event.message_id else '',
        author=None,
        posted_at=event.published_at_text,
        leak_types=[],#
        estimated_volume=None,#
        file_formats=[],
        target_service=event.victim_name,
        domains=[],#
        country=None,
        threat_claim=event.group_name,
        deal_terms=None,
        confidence="medium",#
        screenshot_refs=[],
        osint_seeds={"urls": event.urls},
    )

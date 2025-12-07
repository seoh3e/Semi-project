# app/telegram_venarix.py

import re
from datetime import date
from typing import Optional, List
from app.models import IntermediateEvent, LeakRecord


# ─────────────────────────────────────────────
# 1) raw_text → IntermediateEvent
# ─────────────────────────────────────────────


def parse_venarix(
    raw_text: str, message_id=None, message_url=None
) -> IntermediateEvent:
    """
    VenariX Cyber Feeds 채널 메시지 파서.
    """

    lines = raw_text.splitlines()

    victim = None
    group = None
    published_date_text = None
    urls: List[str] = []

    # 기본 포맷:
    # 🚨 New cyber event 🚨
    #
    # Threat group: nightspire
    #
    # Victim: <img style='width:30px;', src='http://nspiremkiq44z>
    #
    # For detailed insights on this incident, sign up for free at https://www.venarix.com

    for idx, line in enumerate(lines):
        # threat group
        if idx == 2:
            group = line.split(":", 1)[1].strip()

        # victim
        if idx == 4:
            victim = line.split(":", 1)[1].strip()

        # URL
        if idx == 6:
            urls.extend(re.findall(r"(https?://\S+)", line))

    return IntermediateEvent(
        source_channel="@venarix",
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

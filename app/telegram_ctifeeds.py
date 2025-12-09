# app/telegram_ctifeeds.py

import re
from datetime import date
from typing import Optional, List
from .models import IntermediateEvent, LeakRecord
from urllib.parse import urlparse


# ─────────────────────────────────────────────
# 1) raw_text → IntermediateEvent
# ─────────────────────────────────────────────


def parse_ctifeeds(
    raw_text: str, message_id=None, message_url=None
) -> IntermediateEvent:
    """
    ctifeeds 채널 메시지 파서.
    """

    urls: List[str] = []
    victim = None
    group = None
    published_date_text = None

    # 기본 포맷:
    # Recent defacement reported by Hax.or: http://psb.mikenongomulyo.sch.id http://psb.mikenongomulyo.sch.id

    url=re.search(r'(https?://[^\s]+)', raw_text).group(1)

    urls.append(url)

    victim=urlparse(url).netloc

    return IntermediateEvent(
        source_channel="@ctifeeds",
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
        post_id=str(event.message_id) if event.message_id else '',
        author=None,
        posted_at=None,
        leak_types=[],
        estimated_volume=None,
        file_formats=[],
        target_service=event.victim_name,
        domains=event.urls,
        country=None,
        threat_claim=event.group_name,
        deal_terms=None,
        confidence="medium",
        screenshot_refs=[],
        osint_seeds={"urls": event.urls},
    )

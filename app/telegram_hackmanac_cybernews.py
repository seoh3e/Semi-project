# app/telegram_ransomfeednews.py

import re
from datetime import date
from typing import Optional, List

from app.models import IntermediateEvent, LeakRecord


def _extract_first(pattern: str, text: str) -> Optional[str]:
    m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip()


def _extract_urls(text: str) -> List[str]:
    return re.findall(r"https?://\S+", text)


def parse_ransomfeednews(raw_text: str, message_id=None, message_url=None) -> IntermediateEvent:
    """
    RansomFeedNews 채널의 raw 텍스트를 IntermediateEvent 로 변환.
    """
    cleaned = raw_text.replace("\r\n", "\n").strip()

    group = _extract_first(
        r"(?:^|\n)\s*(?:Group|Ransomware\s*group)\s*:\s*(.+)",
        cleaned,
    )
    victim = _extract_first(
        r"(?:^|\n)\s*(?:Victim|Target|Company)\s*:\s*(.+)",
        cleaned,
    )
    published_at_text = _extract_first(
        r"(?:^|\n)\s*(?:Date|Published)\s*:\s*(.+)",
        cleaned,
    )

    urls = _extract_urls(cleaned)
    tags = re.findall(r"#(\w+)", cleaned)

    return IntermediateEvent(
        source_channel="RansomFeedNews",
        raw_text=cleaned,
        message_id=message_id,
        message_url=message_url,
        group_name=group,
        victim_name=victim,
        published_at_text=published_at_text,
        urls=urls,
        tags=tags,
    )


def intermediate_to_leakrecord(event: IntermediateEvent) -> LeakRecord:
    """
    IntermediateEvent(RansomFeedNews) → LeakRecord 간단 변환 (PoC 버전).
    """
    if event.group_name or event.victim_name:
        title = f"{event.group_name or '?'} → {event.victim_name or '?'}"
    else:
        title = "(no title)"

    post_id = str(event.message_id) if event.message_id is not None else ""

    return LeakRecord(
        collected_at=date.today(),
        source="telegram:RansomFeedNews",
        post_title=title,
        post_id=post_id,
        author=None,
        posted_at=None,

        leak_types=[],
        estimated_volume=None,
        file_formats=[],

        target_service=event.victim_name,
        domains=[],
        country=None,

        threat_claim=None,
        deal_terms=None,
        confidence="low",

        screenshot_refs=event.urls,
        osint_seeds={
            "source_channel": event.source_channel,
            "message_url": event.message_url,
            "group_name": event.group_name,
            "victim_name": event.victim_name,
            "published_at_text": event.published_at_text,
            "raw_text": event.raw_text,
        },
    )

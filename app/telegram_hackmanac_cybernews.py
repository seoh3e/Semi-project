# app/telegram_hackmanac_cybernews.py

import re
from datetime import date, datetime
from typing import Optional, List
from app.models import IntermediateEvent, LeakRecord


# ─────────────────────────────────────────────
# 1) raw_text → IntermediateEvent
# ─────────────────────────────────────────────


def parse_hackmanac_cybernews(
    raw_text: str, message_id=None, message_url=None
) -> IntermediateEvent:
    """
    hackmanac_cybernews 채널 메시지 파서.
    """

    lines = raw_text.splitlines()

    victim = None
    group = None
    published_date_text = None
    urls: List[str] = []

    # 기본 포맷:
    # 🚨Cyberattack Alert ‼️
    #
    # 🇿🇲Zambia - National Health Insurance Scheme (NHIS)
    #
    # Nova hacking group claims to have breached National Health Insurance Scheme (NHIS).
    #
    # Allegedly, the attackers exfiltrated patients data.
    #
    # Sector: Insurance
    # Threat class: Cybercrime
    #
    # Observed: Dec 5, 2025
    # Status: Pending verification
    #
    # —
    # About this post:
    # Hackmanac provides early warning and cyber situational awareness through its social channels. This alert is based on publicly available information that our analysts retrieved from clear and dark web sources. No confidential or proprietary data was downloaded, copied, or redistributed, and sensitive details were redacted from the attached screenshot(s).
    #
    # For more details about this incident, our ESIX impact score, and additional context, visit HackRisk.io.

    for idx, line in enumerate(lines):
        # 날짜 정보
        if "Observed:" in line:
            parts = line.split("Observed:")
            if len(parts) > 1:
                published_date_text = parts[1].strip()

        # 그룹명
        if "hacking group" in line:
            parts = line.split("hacking group")
            if len(parts) > 1:
                group = parts[0].strip()

        # 피해자
        if idx == 2:
            parts = line.split(" - ")
            if len(parts) > 1:
                victim = parts[1].strip()

        # URL
        if "Source:" in line:
            parts = line.split("Source:")
            if len(parts) > 1:
                urls.append(parts[1].strip())

    return IntermediateEvent(
        source_channel="@hackmanac_cybernews",
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

    lines = event.raw_text.splitlines()

    for idx, line in enumerate(lines):
        if idx == 2:
            parts = line.split(" - ")
            if len(parts) > 1:
                flag = parts[0].strip()[:2]
                OFFSET = 0x1F1E6  # Regional Indicator Symbol 'A' 시작
                country = "".join(chr(ord(c) - OFFSET + ord("A")) for c in flag)

    return LeakRecord(
        collected_at=date.today(),
        source=event.source_channel,
        post_title=f"{event.group_name or ''} → {event.victim_name or ''}",
        post_id=str(event.message_id) if event.message_id else "",
        author=None,
        posted_at=datetime.strptime(event.published_at, "%b %d, %Y").date(),
        leak_types=[],
        estimated_volume=None,
        file_formats=[],
        target_service=event.victim_name,
        domains=[],
        country=country,
        threat_claim=event.group_name,
        deal_terms=None,
        confidence="medium",
        screenshot_refs=[],
        osint_seeds={"urls": event.urls},
    )

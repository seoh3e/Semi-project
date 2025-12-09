# app/telegram_hackmanac_cybernews.py

import re
from datetime import date,datetime
from typing import Optional, List
from .models import IntermediateEvent, LeakRecord


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

    published_date_text = None
    urls: List[str] = []
    victim = None
    group = None

    # 기본 포맷:
    # 🚨Cyberattack Alert ‼️

    # 🇺🇸USA - Scientology

    # Qilin hacking group claims to have breached Scientology.

    # Sector: Organizations
    # Threat class: Cybercrime
    # Observed: Dec 4, 2025
    # Status: Pending verification

    # —
    # About this post:
    # Hackmanac provides early warning and cyber situational awareness through its social channels. This alert is based on publicly available information that our analysts retrieved from clear and dark web sources. No confidential or proprietary data was downloaded, copied, or redistributed, and sensitive details were redacted from the attached screenshot(s).

    # For more details about this incident, our ESIX impact score, and additional context, visit HackRisk.io.

    for idx, line in enumerate(lines):
        if idx == 0:
            if line != "🚨Cyberattack Alert ‼️":
                break

        if "Observed: " in line:
            published_date_text=datetime.strptime(line.split("Observed: ")[1], "%b %d, %Y").date()

        if "Source: " in line:
            urls=line.split("Source: ")[1]
    else:
        victim=lines[2]

        group=lines[4].split(" hacking group ")[0]

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


def intermediate_to_hackmanac_cybernews_leakrecord(event: IntermediateEvent) -> LeakRecord:
    """
    파싱된 IntermediateEvent → LeakRecord 표준 구조 변환
    """

    status_to_confidence={"Pending verification":"medium","Confirmed":"high"}

    lines = event.raw_text.splitlines()

    estimated_volume=None
    leak_types=[]

    for idx, line in enumerate(lines):
        if " exfiltrated " in line:
            parts=line.split(" exfiltrated ")[1][:-1]
            if " of " in parts:
                estimated_volume=parts.split(" of ")[0]
                if ", including " in parts:
                    leak_types.append(parts.split(", including ")[1][:-1])
            else:
                leak_types.append(parts)

        if "Status: " in line:
            status=line.split("Status: ")[1]

    return LeakRecord(
        collected_at=date.today(),
        source=event.source_channel,
        post_title=f"{event.group_name or ''} → {event.victim_name or ''}",
        post_id=str(event.message_id) if event.message_id else '',
        author=None,
        posted_at=event.published_at_text,
        leak_types=leak_types,
        estimated_volume=estimated_volume,
        file_formats=[],
        target_service=event.victim_name,
        domains=[],
        country=None,
        threat_claim=event.group_name,
        deal_terms=None,
        confidence=status_to_confidence[status],
        screenshot_refs=[],
        osint_seeds={"urls": event.urls},
    )

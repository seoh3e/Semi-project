# app/telegram_ctifeeds.py

from datetime import date
from typing import List
from urllib.parse import urlparse
import re

from .models import IntermediateEvent, LeakRecord
from .enrich_with_osint import enrich_leakrecord_with_osint


# --------------------------------------------------------
# URL → 도메인 추출 유틸
# --------------------------------------------------------
def _extract_domains(urls: List[str]) -> List[str]:
    domains = []
    for u in urls:
        try:
            host = urlparse(u).netloc.lower()
        except Exception:
            continue
        if host and host not in domains:
            domains.append(host)
    return domains


# --------------------------------------------------------
# 1) raw_text → IntermediateEvent
# --------------------------------------------------------
def parse_ctifeeds(
    raw_text: str, message_id=None, message_url=None
) -> IntermediateEvent:

    # URL 추출 (첫 URL 하나만 사용)
    m = re.search(r"(https?://\S+)", raw_text)
    if not m:
        url = None
    else:
        url = m.group(1)

    urls = [url] if url else []

    # victim = 도메인
    victim = urlparse(url).netloc if url else None

    # group = "reported by X" 형식에서 X 추출 (선택적)
    gm = re.search(r"reported by ([^:]+):", raw_text)
    group = gm.group(1).strip() if gm else None

    return IntermediateEvent(
        source_channel="@ctifeeds",
        raw_text=raw_text,
        message_id=message_id,
        message_url=message_url,
        group_name=group,
        victim_name=victim,
        published_at_text=None,   # ctifeeds 메시지에 날짜 없음
        urls=urls,
        tags=[],
    )


# --------------------------------------------------------
# 2) IntermediateEvent → LeakRecord
# --------------------------------------------------------
def intermediate_to_leakrecord(event: IntermediateEvent) -> LeakRecord:

    domains = _extract_domains(event.urls)

    record = LeakRecord(
        collected_at=date.today(),
        source=event.source_channel,
        post_title=f"{event.group_name or ''} → {event.victim_name or ''}",
        post_id=str(event.message_id) if event.message_id else "",
        author=None,
        posted_at=event.published_at_text,
        leak_types=[],
        estimated_volume=None,
        file_formats=[],
        target_service=event.victim_name,
        domains=domains,
        country=None,
        threat_claim=event.group_name,
        deal_terms=None,
        confidence="medium",
        screenshot_refs=[],
        osint_seeds={"urls": event.urls},
    )

    # OSINT 보강
    return enrich_leakrecord_with_osint(record)

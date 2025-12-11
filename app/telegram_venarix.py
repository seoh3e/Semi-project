# app/telegram_venarix.py

from datetime import date
from typing import List
from urllib.parse import urlparse

from .models import IntermediateEvent, LeakRecord
from .enrich_with_osint import enrich_leakrecord_with_osint


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
# raw_text → IntermediateEvent
# --------------------------------------------------------
def parse_venarix(
    raw_text: str, message_id=None, message_url=None
) -> IntermediateEvent:

    lines = raw_text.splitlines()

    group = None
    victim = None
    urls = []

    # Threat group: coinbasecartel
    for line in lines:
        if line.startswith("Threat group:"):
            group = line.split("Threat group:")[1].strip()
            break

    # Victim:
    for line in lines:
        if line.startswith("Victim:"):
            victim = line.split("Victim:")[1].strip()
            break

    # URL
    for line in lines:
        if "http" in line:
            urls.append(line.strip())

    return IntermediateEvent(
        source_channel="@venarix",
        raw_text=raw_text,
        message_id=message_id,
        message_url=message_url,
        group_name=group,
        victim_name=victim,
        published_at_text=None,
        urls=urls,
        tags=[],
    )


# --------------------------------------------------------
# IntermediateEvent → LeakRecord
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

    return enrich_leakrecord_with_osint(record)

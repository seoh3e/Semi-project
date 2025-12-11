# app/telegram_hackmanac_cybernews.py

from datetime import date, datetime
from typing import List
import re
from urllib.parse import urlparse

from .models import IntermediateEvent, LeakRecord
from .enrich_with_osint import enrich_leakrecord_with_osint


# URL → 도메인 추출
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
def parse_hackmanac_cybernews(
    raw_text: str, message_id=None, message_url=None
) -> IntermediateEvent:

    lines = raw_text.splitlines()

    # victim (국가/조직 라인)
    victim = None
    if len(lines) > 2:
        victim = lines[2].strip()

    # group (Qilin hacking group claims...)
    group = None
    for line in lines:
        if "hacking group" in line:
            group = line.split(" hacking group")[0].strip()
            break

    # Observed 날짜
    published_date = None
    for line in lines:
        if "Observed:" in line:
            date_str = line.split("Observed:")[1].strip()
            try:
                published_date = datetime.strptime(date_str, "%b %d, %Y").date()
            except:
                pass

    # Source URL
    urls = []
    for line in lines:
        if "http" in line:
            m = re.search(r"(https?://\S+)", line)
            if m:
                urls.append(m.group(1))

    return IntermediateEvent(
        source_channel="@hackmanac_cybernews",
        raw_text=raw_text,
        message_id=message_id,
        message_url=message_url,
        group_name=group,
        victim_name=victim,
        published_at_text=published_date,
        urls=urls,
        tags=[],
    )


# --------------------------------------------------------
# 2) IntermediateEvent → LeakRecord
# --------------------------------------------------------
def intermediate_to_leakrecord(event: IntermediateEvent) -> LeakRecord:

    domains = _extract_domains(event.urls)

    # Status → confidence 매핑
    status_to_confidence = {
        "Pending verification": "medium",
        "Confirmed": "high",
    }

    status = "Pending verification"
    for line in event.raw_text.splitlines():
        if "Status:" in line:
            status = line.split("Status:")[1].strip()

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
        confidence=status_to_confidence.get(status, "medium"),
        screenshot_refs=[],
        osint_seeds={"urls": event.urls},
    )

    return enrich_leakrecord_with_osint(record)

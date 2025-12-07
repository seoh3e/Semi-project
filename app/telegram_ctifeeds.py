import re
from urllib.parse import urlparse
from datetime import date
from typing import Optional, List, Dict

from .models import IntermediateEvent, LeakRecord


# 기본 포맷:
# Recent defacement reported by Hax.or: https://sadra-kss.ir https://sadra-kss.ir


def extract_urls(text: str) -> List[str]:
    urls = re.findall(r"(https?://\S+)", text)
    cleaned = [u.rstrip(").,") for u in urls]
    return list(dict.fromkeys(cleaned))


def domain_from_url(url: str) -> Optional[str]:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return None


def extract_attacker_aliases(text: str) -> List[str]:
    aliases: List[str] = []

    m = re.search(r"reported by\s+([^:]+):", text, re.IGNORECASE)
    if m:
        aliases.append(m.group(1).strip())

    m = re.search(r"Hacked BY\s+([^\s]+)", text, re.IGNORECASE)
    if m:
        aliases.append(m.group(1).strip())

    return list(dict.fromkeys(aliases))


def parse_ctifeeds(
    raw_text: str, message_id=None, message_url=None
) -> IntermediateEvent:
    lower = raw_text.lower()

    urls = extract_urls(raw_text)
    first_url = urls[0] if urls else None
    domain = domain_from_url(first_url) if first_url else None

    attacker_aliases = extract_attacker_aliases(raw_text)
    group = attacker_aliases[0] if attacker_aliases else None

    tags: List[str] = []
    if "defacement" in lower or "hacked by" in lower:
        tags.append("web_defacement")
    if "data breach" in lower or "breach" in lower or "leak" in lower:
        tags.append("data_breach")

    return IntermediateEvent(
        source_channel="@ctifeeds",
        raw_text=raw_text.strip(),
        message_id=message_id,
        message_url=message_url,
        group_name=group,
        victim_name=domain,
        published_at_text=None,
        urls=urls,
        tags=tags,
    )


def intermediate_to_leakrecord(event: IntermediateEvent) -> LeakRecord:
    leak_types: List[str] = []
    if "web_defacement" in (event.tags or []):
        leak_types.append("web_defacement")
    if "data_breach" in (event.tags or []):
        leak_types.append("data_breach")

    target_service_val = event.victim_name
    domains_val = [event.victim_name] if event.victim_name else []

    osint_seeds: Dict = {
        "urls": event.urls,
        "attacker_aliases": [event.group_name] if event.group_name else [],
        "raw_text": event.raw_text,
        "message_url": event.message_url,
    }

    return LeakRecord(
        collected_at=date.today(),
        source=event.source_channel,
        post_title=event.raw_text,
        post_id=str(event.message_id) if event.message_id else "",
        author=None,
        posted_at=None,
        leak_types=leak_types,
        estimated_volume=None,
        file_formats=[],
        target_service=target_service_val,
        domains=domains_val,
        country=None,
        threat_claim=event.raw_text,
        deal_terms=None,
        confidence="medium",
        screenshot_refs=[],
        osint_seeds=osint_seeds,
    )

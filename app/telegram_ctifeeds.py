#telegram_ctifeeds.py

import re
from urllib.parse import urlparse
from datetime import date
from typing import Optional, List, Dict

from pyrogram import Client
from pyrogram.types import Message

from app.models import IntermediateEvent, LeakRecord
from app.storage import add_leak_record
from app.notifier import notify_new_leak

API_ID = 34221825
API_HASH = "44a948711e6034324886bebc6abb0a5d"
CHANNEL = "@ctifeeds"

app = Client("ctifeeds_session", api_id=API_ID, api_hash=API_HASH)

def extract_urls(text: str) -> List[str]:
    urls = re.findall(r"(https?://\S+)", text)
    # 뒤에 따라붙는 괄호/쉼표/마침표 제거
    cleaned = [u.rstrip(").,") for u in urls]
    # 중복 제거(순서 유지)
    return list(dict.fromkeys(cleaned))


def extract_first_url(text: str) -> Optional[str]:
    urls = extract_urls(text)
    return urls[0] if urls else None


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


def parse_ctifeeds(raw_text: str, message_id=None, message_url=None) -> IntermediateEvent:
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
        source_channel="Telegram:Cyber Threat Intelligence Feeds",
        raw_text=raw_text,
        message_id=message_id,
        message_url=message_url,
        group_name=group,
        victim_name=domain,
        published_at=None,
        urls=urls,
        tags=tags,
    )


def intermediate_to_leakrecord(
    event: IntermediateEvent,
    posted_at=None,
    author=None,
) -> LeakRecord:

    leak_types: List[str] = []
    if "web_defacement" in (event.tags or []):
        leak_types.append("web_defacement")
    if "data_breach" in (event.tags or []):
        leak_types.append("data_breach")

    # 서비스/도메인 정리
    target_service_val = event.victim_name
    domains_val = [event.victim_name] if event.victim_name else []

    osint_seeds: Dict = {
        "urls": event.urls,
        "attacker_aliases": [event.group_name] if event.group_name else [],
        "raw_text": event.raw_text,
    }

    return LeakRecord(
        collected_at=date.today(),
        source=event.source_channel,
        post_title=event.raw_text,  # ctifeeds는 문장 자체를 제목으로
        post_id=str(event.message_id) if event.message_id else "",
        author=author,
        posted_at=posted_at,

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


def fetch_ctifeeds(limit: int = 50) -> None:
    parsed_count = 0
    관심키워드 = ("defacement", "hacked by", "data breach", "breach", "leak")

    with app:
        for message in app.get_chat_history(CHANNEL, limit=limit):
            text = (message.text or message.caption or "").strip()
            if not text:
                continue

            lower = text.lower()
            if not any(k in lower for k in 관심키워드):
                continue

            # 1) raw → intermediate
            event = parse_ctifeeds(
                text,
                message_id=getattr(message, "id", None),
                message_url=getattr(message, "link", None),
            )

            # 2) intermediate → record
            posted_at_val = message.date.date() if getattr(message, "date", None) else None
            author_val = getattr(message.from_user, "username", None) if getattr(message, "from_user", None) else None

            record = intermediate_to_leakrecord(
                event,
                posted_at=posted_at_val,
                author=author_val,
            )

            add_leak_record(record)
            notify_new_leak(record)
            parsed_count += 1

    print(f"[INFO] ctifeeds에서 {parsed_count}건의 유출/defacement 이벤트를 파싱했습니다.")


if __name__ == "__main__":
    fetch_ctifeeds(limit=30)

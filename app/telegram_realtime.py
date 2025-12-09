# app/telegram_realtime.py

import os
import asyncio
from telethon import TelegramClient, events

from .telegram_RansomFeedNews import (
    parse_RansomFeedNews,
    intermediate_to_leakrecord as ransomfeed_to_leakrecord,
)
from .telegram_ctifeeds import (
    parse_ctifeeds,
    intermediate_to_leakrecord as ctifeeds_to_leakrecord,
)
from .telegram_hackmanac_cybernews import (
    parse_hackmanac_cybernews,
    intermediate_to_leakrecord as hackmanac_to_leakrecord,
)
from .telegram_venarix import (
    parse_venarix,
    intermediate_to_leakrecord as venarix_to_leakrecord,
)
from .models import LeakRecord
from .storage import add_leak_record
from .notifier import notify_new_leak


API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION = "semi_project"


def process_record(record: LeakRecord) -> None:
    add_leak_record(record)
    notify_new_leak(record)


async def main() -> None:
    client = TelegramClient(SESSION, API_ID, API_HASH)

    @client.on(events.NewMessage(chats=["RansomFeedNews"]))
    async def handler(event) -> None:
        msg = event.message
        text = msg.message or ""
        if not text.strip():
            return

        message_id = msg.id
        message_url = f"https://t.me/RansomFeedNews/{message_id}"

        ev = parse_ransomfeednews(
            text,
            message_id=message_id,
            message_url=message_url,
        )

        if not ev.group_name and not ev.victim_name:
            return

        record = intermediate_to_leakrecord(ev)
        process_record(record)

        print(
            "[REALTIME LEAK] RansomFeedNews",
            ev.group_name or "?",
            "→",
            ev.victim_name or "?",
        )

    async with client:
        print("[INFO] 실시간 모니터링 시작 (Ctrl+C로 종료)")
        await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())

# app/telegram_realtime.py

import os
import asyncio
from telethon import TelegramClient, events

from .telegram_ransomfeednews import parse_ransomfeednews, intermediate_to_leakrecord
from .models import LeakRecord
from .storage import add_leak_record
from .notifier import notify_new_leak

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION = "semi_project"


def process_record(record: LeakRecord):
    add_leak_record(record)
    notify_new_leak(record)


async def main():
    client = TelegramClient(SESSION, API_ID, API_HASH)

    @client.on(events.NewMessage(chats=["RansomFeedNews"]))
    async def handler(event):
        msg = event.message
        text = msg.message or ""
        if not text.strip():
            return

        message_id = msg.id
        message_url = f"https://t.me/RansomFeedNews/{message_id}"

        ev = parse_ransomfeednews(text, message_id=message_id, message_url=message_url)
        if not ev.group_name and not ev.victim_name:
            return

        record = intermediate_to_leakrecord(ev)
        process_record(record)

        print("[REALTIME LEAK] RansomFeedNews",
              ev.group_name or "?", "→", ev.victim_name or "?")

    async with client:
        print("[INFO] 실시간 모니터링 시작 (Ctrl+C로 종료)")
        await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())

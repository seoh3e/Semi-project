"""
각 텔레그램 채널에서 '최근 N개' 메시지를 가져와
채널별 파서로 IntermediateEvent → LeakRecord 변환 후
한 번에 leak_summary.csv / leak_summary.json 으로 저장하는 배치 스크립트.
"""

from __future__ import annotations
import asyncio
from typing import List

from telethon import TelegramClient
from .models import IntermediateEvent, LeakRecord
from .telegram_runner import (
    API_ID, API_HASH, SESSION,
    CHANNEL_PARSERS   # username → (parse_func, to_leakrecord)
)
from .storage import save_leak_summary


SUMMARY_MESSAGES_PER_CHANNEL = 10  # 채널당 최근 10개


async def collect_channel_records(
    client: TelegramClient,
    channel_username: str
) -> List[LeakRecord]:
    """
    telegram_runner.handle_channel_messages 와 거의 동일하지만,
    process_leak_record()를 호출하지 않고,
    LeakRecord만 리스트로 모아서 반환하는 버전.
    """

    parse_func, to_leakrecord = CHANNEL_PARSERS[channel_username]
    records: List[LeakRecord] = []

    print(f"[SUMMARY] 채널 수집 시작: @{channel_username}")

    async for msg in client.iter_messages(channel_username, limit=SUMMARY_MESSAGES_PER_CHANNEL):
        text = msg.message or ""
        if not text.strip():
            continue

        event: IntermediateEvent = parse_func(
            raw_text=text,
            message_id=msg.id,
            message_url=f"https://t.me/{channel_username}/{msg.id}",
        )

        if not event.group_name and not event.victim_name:
            continue

        record = to_leakrecord(event)
        records.append(record)

    print(f"[SUMMARY] 채널 수집 완료: @{channel_username}, {len(records)}건")
    return records


async def main() -> None:
    client = TelegramClient(SESSION, API_ID, API_HASH)

    all_records: List[LeakRecord] = []

    async with client:
        me = await client.get_me()
        print(f"[SUMMARY] 로그인 계정: {me.username or me.first_name}")

        for username in CHANNEL_PARSERS.keys():
            channel_records = await collect_channel_records(client, username)
            all_records.extend(channel_records)

    print(f"[SUMMARY] 전체 수집 완료: 총 {len(all_records)}건")
    save_leak_summary(all_records)
    print("[SUMMARY] leak_summary.csv / leak_summary.json 저장 완료")


if __name__ == "__main__":
    asyncio.run(main())

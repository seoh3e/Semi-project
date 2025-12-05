# app/telegram_runner.py

"""
텔레그램 채널에서 실제 메시지를 읽어와서
RansomFeedNews 파서 → IntermediateEvent → LeakRecord → 저장/알림
까지 한 번에 처리하는 실행 스크립트.
"""

from __future__ import annotations

import os
import asyncio
from typing import Callable, Dict, Tuple

from telethon import TelegramClient

from .models import IntermediateEvent, LeakRecord
from .storage import add_leak_record
from .notifier import notify_new_leak
from .telegram_ransomfeednews import (
    parse_ransomfeednews,
    intermediate_to_leakrecord,
)
from .telegram_ctifeeds_parser import (
    parse_ctifeeds,
    intermediate_to_leakrecord as ctifeeds_to_leakrecord,
)

# ───────────────────── 설정 ─────────────────────

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION = "semi_project"  # 로그인 테스트 때 사용한 이름과 동일

# username → (raw→IntermediateEvent, IntermediateEvent→LeakRecord)
ChannelParser = Tuple[
    Callable[..., IntermediateEvent],
    Callable[[IntermediateEvent], LeakRecord],
]

CHANNEL_PARSERS: Dict[str, ChannelParser] = {
    "RansomFeedNews": (parse_ransomfeednews, intermediate_to_leakrecord),
    "ctifeeds": (parse_ctifeeds, ctifeeds_to_leakrecord),
}

MESSAGES_PER_CHANNEL = 50  # 채널당 최근 몇 개까지 처리할지


# ───────────── 공통 처리 함수 ─────────────

def process_leak_record(record: LeakRecord) -> None:
    """LeakRecord를 저장하고 알림을 보내는 공통 함수."""
    add_leak_record(record)
    notify_new_leak(record)


async def handle_channel_messages(
    client: TelegramClient,
    channel_username: str,
    parser_funcs: ChannelParser,
) -> None:
    """
    특정 채널의 최근 메시지들을 순회하면서
    파서 → LeakRecord → 저장/알림까지 처리.
    """
    parse_func, to_leakrecord = parser_funcs

    print(f"\n[INFO] 채널 처리 시작: @{channel_username}")

    async for msg in client.iter_messages(channel_username, limit=MESSAGES_PER_CHANNEL):
        text = msg.message or ""
        if not text.strip():
            continue  # 텍스트 없는 메시지는 건너뜀

        message_id = msg.id
        message_url = f"https://t.me/{channel_username}/{message_id}"

        # 1) raw → IntermediateEvent
        event: IntermediateEvent = parse_func(
            raw_text=text,
            message_id=message_id,
            message_url=message_url,
        )

        # 최소 필터링: group / victim 둘 다 없으면 의미 없는 메시지로 간주
        if not event.group_name and not event.victim_name:
            # print(f"[SKIP] @{channel_username} #{message_id} (no group/victim)")
            continue

        # 2) IntermediateEvent → LeakRecord
        record: LeakRecord = to_leakrecord(event)

        # 3) 저장 + 알림
        process_leak_record(record)

        print(
            f"[NEW LEAK DETECTED] @{channel_username} #{message_id} "
            f"{event.group_name or '?'} → {event.victim_name or '?'}"
        )

    print(f"[INFO] 채널 처리 완료: @{channel_username}")


async def main() -> None:
    """등록된 모든 채널에 대해 메시지를 처리하는 메인 함수."""
    client = TelegramClient(SESSION, API_ID, API_HASH)

    async with client:
        me = await client.get_me()
        print(f"[INFO] 로그인 계정: {me.username or me.first_name}")

        for username, parser_funcs in CHANNEL_PARSERS.items():
            await handle_channel_messages(client, username, parser_funcs)

    print("[INFO] 모든 채널 처리 완료, 프로그램 종료")


if __name__ == "__main__":
    asyncio.run(main())

"""
텔레그램 채널에서 실제 메시지를 읽어와서
각 채널별 파서로
    raw 텍스트 → IntermediateEvent → LeakRecord → 저장/알림
까지 한 번에 처리하는 실행 스크립트.
"""

from __future__ import annotations

import os
import asyncio
from typing import Callable, Dict, Tuple

from telethon import TelegramClient

# 메인 데모에서 쓰던 공통 파이프라인 재사용 (JSON + CSV 저장 + 콘솔 알림)
from .main_demo_telegram import process_leak_record

from .models import IntermediateEvent, LeakRecord

# ─────────────────────────────────────
# 채널별 파서 import  (파일 이름에 맞춰서 수정)
# ─────────────────────────────────────

# 1) RansomFeedNews  → 파일: telegram_RansomFeedNews.py
from .telegram_RansomFeedNews import (
    parse_RansomFeedNews,
    intermediate_to_leakrecord as ransomfeednews_to_leakrecord,
)

# 2) ctifeeds → 파일: telegram_ctifeeds.py
from .telegram_ctifeeds import (
    parse_ctifeeds,
    intermediate_to_leakrecord as ctifeeds_to_leakrecord,
)

# 3) hackmanac_cybernews → 파일: telegram_hackmanac_cybernews.py
from .telegram_hackmanac_cybernews import (
    parse_hackmanac_cybernews,
    intermediate_to_leakrecord as hackmanac_to_leakrecord,
)

# 4) venarix → 파일: telegram_venarix.py
from .telegram_venarix import (
    parse_venarix,
    intermediate_to_leakrecord as venarix_to_leakrecord,
)

# ─────────────────────────────────────
# 설정
# ─────────────────────────────────────

API_ID = 33760407
API_HASH = "f0ab2298a54a0ec30fdd1b7111e66e8a"
SESSION = "semi_project"  # 로그인 테스트 때 사용한 세션 이름과 동일하게

# username → (raw→IntermediateEvent, IntermediateEvent→LeakRecord)
ChannelParser = Tuple[
    Callable[..., IntermediateEvent],
    Callable[[IntermediateEvent], LeakRecord],
]

CHANNEL_PARSERS: Dict[str, ChannelParser] = {
    # 실제 텔레그램 채널 username 기준!
    "RansomFeedNews": (parse_RansomFeedNews, ransomfeednews_to_leakrecord),
    "ctifeeds": (parse_ctifeeds, ctifeeds_to_leakrecord),
    "hackmanac_cybernews": (parse_hackmanac_cybernews, hackmanac_to_leakrecord),
    "venarix": (parse_venarix, venarix_to_leakrecord),
}

MESSAGES_PER_CHANNEL = 50  # 채널당 최근 몇 개까지 처리할지


# ─────────────────────────────────────
# 공통 처리 함수
# ─────────────────────────────────────

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
            # 텍스트 없는 메시지는 건너뜀
            continue

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

        # 3) 공통 파이프라인 태우기 (JSON + CSV + 콘솔 알림)
        process_leak_record(record)

        print(
            f"[NEW LEAK DETECTED] @{channel_username} #{message_id} "
            f"{event.group_name or '?'} → {event.victim_name or '?'}"
        )

    print(f"[INFO] 채널 처리 완료: @{channel_username}")


# ─────────────────────────────────────
# 엔트리 포인트
# ─────────────────────────────────────

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

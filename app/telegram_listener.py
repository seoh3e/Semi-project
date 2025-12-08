# app/telegram_listener.py
"""
텔레그램 실시간 Listener → 파이프라인 연결 스크립트

- Telethon으로 텔레그램 채널 새 메시지를 실시간으로 수신
- 채널별 파서(telegram_*.py) or 공통 parser.py 에 태워서
  LeakRecord 생성
- storage.add_leak_record + notifier.notify_new_leak 까지 자동 수행
"""

from __future__ import annotations

import os
import asyncio
from typing import Optional

from telethon import TelegramClient, events  # pip install telethon

from .parser import parse_telegram_message
from .main_demo_telegram import process_leak_record

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


# -----------------------------------------------------------------------------
#  환경 설정 (API 키는 .env 또는 환경변수로 관리 추천)
# -----------------------------------------------------------------------------
API_ID = int(os.getenv("TG_API_ID", "0"))
API_HASH = os.getenv("TG_API_HASH", "")
SESSION_NAME = os.getenv("TG_SESSION_NAME", "semi_project_session")

# 모니터링할 채널 username 목록 (@ 없이)
# 실제 채널 username에 맞게 수정하면 됨
CHANNEL_USERNAMES = {
    "RansomFeedNews": "RansomFeedNews",
    "ctifeeds": "ctifeeds",
    "hackmanac_cybernews": "hackmanac_cybernews",
    "venarix": "venarix",  # 실제 venarix 채널 username에 맞게 조정
}


# -----------------------------------------------------------------------------
#  채널별 핸들러 로직
# -----------------------------------------------------------------------------
async def handle_ransomfeednews(event) -> None:
    text = event.raw_text.strip()
    msg_id = event.id
    chat = await event.get_chat()
    username = getattr(chat, "username", None)

    message_url: Optional[str] = (
        f"https://t.me/{username}/{msg_id}" if username else None
    )

    inter = parse_RansomFeedNews(
        raw_text=text,
        message_id=msg_id,
        message_url=message_url,
    )

    if not inter.group_name and not inter.victim_name:
        print("[SKIP] RansomFeedNews event without group/victim")
        return

    record = ransomfeed_to_leakrecord(inter)
    process_leak_record(record)


async def handle_ctifeeds(event) -> None:
    text = event.raw_text.strip()
    msg_id = event.id
    chat = await event.get_chat()
    username = getattr(chat, "username", None)

    message_url: Optional[str] = (
        f"https://t.me/{username}/{msg_id}" if username else None
    )

    inter = parse_ctifeeds(
        raw_text=text,
        message_id=msg_id,
        message_url=message_url,
    )

    if not inter.group_name and not inter.victim_name:
        print("[SKIP] ctifeeds event without group/victim")
        return

    record = ctifeeds_to_leakrecord(inter)
    process_leak_record(record)


async def handle_hackmanac(event) -> None:
    text = event.raw_text.strip()
    msg_id = event.id
    chat = await event.get_chat()
    username = getattr(chat, "username", None)

    message_url: Optional[str] = (
        f"https://t.me/{username}/{msg_id}" if username else None
    )

    inter = parse_hackmanac_cybernews(
        raw_text=text,
        message_id=msg_id,
        message_url=message_url,
    )

    if not inter.group_name and not inter.victim_name:
        print("[SKIP] hackmanac_cybernews event without group/victim")
        return

    record = hackmanac_to_leakrecord(inter)
    process_leak_record(record)


async def handle_venarix(event) -> None:
    text = event.raw_text.strip()
    msg_id = event.id
    chat = await event.get_chat()
    username = getattr(chat, "username", None)

    message_url: Optional[str] = (
        f"https://t.me/{username}/{msg_id}" if username else None
    )

    inter = parse_venarix(
        raw_text=text,
        message_id=msg_id,
        message_url=message_url,
    )

    if not inter.group_name and not inter.victim_name:
        print("[SKIP] venarix event without group/victim")
        return

    record = venarix_to_leakrecord(inter)
    process_leak_record(record)


async def handle_generic(event) -> None:
    """
    위 네 개 채널이 아닌 곳에서 온 메시지는
    공통 parser.parse_telegram_message()에 태워서 처리.
    (DarkForum 스타일 같은 일반 포맷용)
    """
    text = event.raw_text.strip()
    if not text:
        return

    record = parse_telegram_message(text)
    process_leak_record(record)


# -----------------------------------------------------------------------------
#  Telethon 이벤트 루프
# -----------------------------------------------------------------------------
def _get_username_from_event_chat(chat) -> Optional[str]:
    """
    chat 객체에서 username을 뽑아서 소문자로 정규화.
    """
    if not chat:
        return None
    username = getattr(chat, "username", None)
    if not username:
        return None
    return username.lower()


async def main() -> None:
    if API_ID == 0 or not API_HASH:
        raise RuntimeError(
            "TG_API_ID / TG_API_HASH 환경변수를 먼저 설정해주세요."
        )

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

    @client.on(events.NewMessage)
    async def handler(event):
        chat = await event.get_chat()
        username = _get_username_from_event_chat(chat)

        # 디버그용 로그
        print(
            f"[NEW MESSAGE] chat={username or chat.id} id={event.id} "
            f"len={len(event.raw_text)}"
        )

        if not username:
            # username 없는 경우는 generic 파서로
            await handle_generic(event)
            return

        # 소문자로 비교
        u = username.lower()

        if u == CHANNEL_USERNAMES["RansomFeedNews"].lower():
            await handle_ransomfeednews(event)
        elif u == CHANNEL_USERNAMES["ctifeeds"].lower():
            await handle_ctifeeds(event)
        elif u == CHANNEL_USERNAMES["hackmanac_cybernews"].lower():
            await handle_hackmanac(event)
        elif u == CHANNEL_USERNAMES["venarix"].lower():
            await handle_venarix(event)
        else:
            # 등록 안 된 채널은 generic 포맷으로 시도
            await handle_generic(event)

    await client.start()
    print("✅ Telegram Listener started. Waiting for new messages...")
    print("   모니터링 채널:", ", ".join(CHANNEL_USERNAMES.values()))
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())

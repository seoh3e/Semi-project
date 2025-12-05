# app/main_from_telegram_hackmanac_cybernews.py
import asyncio
from telethon import TelegramClient
from .parser_hackmanac_cybernews import parse_telegram_message
from .storage import add_leak_record
from .notifier import notify_new_leak

# ==========================================
# Telethon 설정
# ==========================================
api_id = 33634099
api_hash = "f313b1b911e2abe7044049359a8ddee9"
channel = "@hackmanac_cybernews"

# ==========================================
# 메시지 처리 함수
# ==========================================
async def run_from_telegram_hackmanac_cybernews():
    print("Starting Telethon client...")

    # 1) Telethon 연결
    async with TelegramClient("session_demo", api_id, api_hash) as client:
        print("Client connected.")

        # 2) 최대 200개 메시지 가져오기
        messages = await client.get_messages(channel, limit=1)
        if not messages:
            print("채널에 메시지가 없습니다.")
            return

        # 3) 각 메시지 처리
        for message in messages:
            if not (getattr(message, "raw_text", None) or getattr(message, "message", "") or "").startswith("🚨Cyberattack Alert ‼️"):
                continue

            # 4) 메시지를 LeakRecord로 변환
            record = parse_telegram_message(message)

            # 6) 선택: CSV/JSON 저장
            add_leak_record(record)

            # 7) 선택: 알림 출력
            notify_new_leak(record)

# ==========================================
# 실행
# ==========================================
if __name__ == "__main__":
    asyncio.run(run_from_telegram_hackmanac_cybernews())

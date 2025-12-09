# app/test_fetch_ransomfeednews.py

import os
import asyncio
from telethon import TelegramClient

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION = "semi_project"   # login_test 때 썼던 이름과 동일해야 함


async def main():
    client = TelegramClient(SESSION, API_ID, API_HASH)

    async with client:
        print("[INFO] 텔레그램 로그인 완료")

        channel = "RansomFeedNews"  # 다른 채널 테스트할 땐 여기만 바꾸면 됨

        print(f"[INFO] @{channel} 최근 메시지 5개 가져오는 중...\n")

        async for msg in client.iter_messages(channel, limit=5):
            print("--------------------------------------------------")
            print("Message ID:", msg.id)
            print("Date      :", msg.date)
            print("Text:")
            print(msg.message)
            print()

    print("[INFO] 완료")


if __name__ == "__main__":
    asyncio.run(main())

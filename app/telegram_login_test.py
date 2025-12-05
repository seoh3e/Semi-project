from telethon import TelegramClient
import os
import asyncio

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION = "semi_project"

async def main():
    client = TelegramClient(SESSION, API_ID, API_HASH)
    async with client:
        me = await client.get_me()
        print("로그인 성공!")
        print("Your Telegram account:", me.username or me.first_name)

if __name__ == "__main__":
    asyncio.run(main())

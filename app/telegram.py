#channel에서 최근 피드 100개 수집
from pyrogram import Client

api_id = 33634099
api_hash = "f313b1b911e2abe7044049359a8ddee9"
channel = "@venarix"

app = Client("session", api_id=api_id, api_hash=api_hash)

with app:
    for message in app.get_chat_history(channel, limit=100):
        if message.text:
            with open("feed.txt", "a", encoding="utf-8") as f:
                f.write(message.text + "\n")
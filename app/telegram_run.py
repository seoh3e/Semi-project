#channel에서 실시간 피드 수집
from pyrogram import Client, filters

app = Client("session", api_id=33634099, api_hash="f313b1b911e2abe7044049359a8ddee9")

@app.on_message(filters.chat("@venarix"))
def handler(client, message):
    if message.text:
        with open("feed_live.txt", "a", encoding="utf-8") as f:
            f.write(message.text + "\n")

app.run()
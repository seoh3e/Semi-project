# app/telegram_login_test.py
from telethon import TelegramClient

API_ID = 33760407      # 여기에 본인 api_id 숫자
API_HASH = "f0ab2298a54a0ec30fdd1b7111e66e8a"  # 본인 api_hash
SESSION_NAME = "semi_project_session"          # 세션 파일 이름

def main():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    client.start()   # 처음 실행 시 터미널에서 전화번호, 인증코드 입력
    print("로그인 세션 생성 완료! (세션 파일이 생성되었습니다.)")

if __name__ == "__main__":
    main()

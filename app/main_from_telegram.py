# app/main_from_telegram.py
from .parser import parse_telegram_message
from .storage import add_leak_record
from .notifier import notify_new_leak


def run_from_telegram_demo() -> None:
    """
    텔레그램 피드에서 메시지 1개를 받았다고 가정하고,
    → 파싱 → 저장(CSV/JSON) → 알림 출력
    까지 한 번에 실행하는 데모.
    """

    # 실제로는 여기 raw_message를
    #  - 텔레그램 봇/피드 모듈에서 받아서 넣어주면 됨
    raw_message = """[DarkForum A] KR education site users dump 2024
Target: Example Korean Education Service (edu-example.co.kr)
Leak: email, password_hash, phone
Volume: 15000
Confidence: high
"""

    # 1) 텔레그램 메시지를 LeakRecord로 변환
    record = parse_telegram_message(raw_message)

    # 2) CSV/JSON에 저장
    add_leak_record(record)

    # 3) 알림 출력
    notify_new_leak(record)


if __name__ == "__main__":
    run_from_telegram_demo()

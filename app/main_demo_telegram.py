# app/main_demo_telegram.py

"""
텔레그램 기반 피드들을 '샘플 메시지'로 테스트하기 위한 데모 스크립트.

- 공통 처리 흐름:
    raw 텍스트              →  (채널별 parser)
    IntermediateEvent       →  LeakRecord
    LeakRecord              →  저장 + 알림

- 현재 구현된 채널:
    - RansomFeedNews
    - hackmanac_cybernews(구현 중)
"""

from __future__ import annotations

from .parser import parse_telegram_message          # 기존 일반 텔레그램 포맷용 파서 (DarkForum 스타일 등)
from .storage import add_leak_record
from .notifier import notify_new_leak
from .models import LeakRecord
from .telegram_ransomfeednews import (
    parse_ransomfeednews,
    parse_hackmanac_cybernews,
    intermediate_to_leakrecord,
)


# ---------------------------------------------------------------------------
# 공통 처리 유틸
# ---------------------------------------------------------------------------

def process_leak_record(record: LeakRecord) -> None:
    """
    LeakRecord를 공통 파이프라인에 태우는 함수.
    - CSV/JSON 저장
    - 콘솔/슬랙 등 알림 출력
    """
    # 1) 저장
    add_leak_record(record)

    # 2) 알림
    notify_new_leak(record)


# ---------------------------------------------------------------------------
# 1. 기존 일반 텔레그램 메시지 데모 (DarkForum 같은 포맷)
# ---------------------------------------------------------------------------

def run_generic_telegram_demo() -> None:
    """
    기존에 있던 단일 텔레그램 메시지 데모.
    parser.parse_telegram_message() 를 테스트할 때 사용.
    """
    raw_message = """
[DarkForum B] KR gov users leaked 2025

target service : Example Korean Gov Portal (gov-example.go.kr)
LEAK TYPES : email / password_hash / address
volume : 20,000
CONFIDENCE : HIGH
    """.strip()

    # 1) 텔레그램 메시지를 LeakRecord로 변환
    record: LeakRecord = parse_telegram_message(raw_message)

    # 2) 공통 파이프라인 태우기
    process_leak_record(record)


# ---------------------------------------------------------------------------
# 2. RansomFeedNews 전용 데모
# ---------------------------------------------------------------------------

def run_ransomfeednews_demo() -> None:
    """
    RansomFeedNews 채널에서 온 메시지를 예시로 사용하는 데모.

    실제 텔레그램 API 연동 없이,
    '이런 형식의 텍스트가 왔다'고 가정하고 파이프라인을 테스트한다.
    """
    raw_message = """
Group: LockBit
Victim: Example Corp
Country: USA
Website: https://www.example.com
Date: 2025-01-01
Leak: https://ransomleaks.com/post/12345
    """.strip()

    # 1) raw → IntermediateEvent
    event = parse_ransomfeednews(
        raw_text=raw_message,
        message_id=123,                      # 데모용 임의 값
        message_url="https://t.me/RansomFeedNews/123",
    )

    # group / victim 둘 다 없으면 의미 없는 메시지로 간주
    if not event.group_name and not event.victim_name:
        print("[SKIP] RansomFeedNews event without group/victim")
        return

    # 2) IntermediateEvent → LeakRecord
    record: LeakRecord = intermediate_to_leakrecord(event)

    # 3) 공통 파이프라인 태우기
    process_leak_record(record)


# ---------------------------------------------------------------------------
# 3. hackmanac_cybernews 전용 데모
# ---------------------------------------------------------------------------

def run_hackmanac_cybernews_demo() -> None:
    """
    hackmanac_cybernews 채널에서 온 메시지를 예시로 사용하는 데모.

    실제 텔레그램 API 연동 없이,
    '이런 형식의 텍스트가 왔다'고 가정하고 파이프라인을 테스트한다.
    """
    raw_message = "🚨Cyberattack Alert ‼️\n\n🇿🇲Zambia - National Health Insurance Scheme (NHIS)\n\nNova hacking group claims to have breached National Health Insurance Scheme (NHIS).\n\nAllegedly, the attackers exfiltrated patients data.\n\nSector: Insurance\nThreat class: Cybercrime\n\nObserved: Dec 5, 2025\nStatus: Pending verification\n\nSource: https://therecord.media/askul-resumes-limited-ordering-following-ransomware-attack"

    if raw_message[:21] != "🚨Cyberattack Alert ‼️":
        return

    # 1) raw → IntermediateEvent
    event = parse_hackmanac_cybernews(
        raw_text=raw_message,
        message_id=123,                      # 데모용 임의 값
        message_url="https://t.me/hackmanac_cybernews/123",
    )
    print(event)
    # group / victim 둘 다 없으면 의미 없는 메시지로 간주
    if not event.group_name and not event.victim_name:
        print("[SKIP] hackmanac_cybernews event without group/victim")
        return

    # 2) IntermediateEvent → LeakRecord
    record: LeakRecord = intermediate_to_leakrecord(event)
    print(record)
    # 3) 공통 파이프라인 태우기
    process_leak_record(record)


# ---------------------------------------------------------------------------
# 엔트리 포인트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 필요에 따라 어떤 데모를 돌릴지 선택하면 됨.

    # 1) 기존 일반 텔레그램 포맷 테스트
    # run_generic_telegram_demo()

    # 2) RansomFeedNews 채널 포맷 테스트
    run_ransomfeednews_demo()

    # 3) hackmanac_cybernews 채널 포맷 테스트
    # run_hackmanac_cybernews_demo()

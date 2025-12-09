# app/main_demo_telegram.py

"""
텔레그램 기반 피드들을 '샘플 메시지'로 테스트하기 위한 데모 스크립트.

- 공통 처리 흐름:
    raw 텍스트              →  (채널별 parser)
    IntermediateEvent       →  LeakRecord
    LeakRecord              →  저장 + 알림

- 현재 구현된 채널:
    - RansomFeedNews
    - ctifeeds
    - hackmanac_cybernews
    - venarix
"""

from __future__ import annotations

from .parser import parse_telegram_message  # 기존 일반 텔레그램 포맷용 파서 (DarkForum 스타일 등)
from .storage import add_leak_record
from .notifier import notify_new_leak
from .models import LeakRecord
from .telegram_RansomFeedNews import (
    parse_RansomFeedNews,
    intermediate_to_RansomFeedNews_leakrecord,
)
from .telegram_ctifeeds import (
    parse_ctifeeds,
    intermediate_to_ctifeeds_leakrecord,
)
from .telegram_hackmanac_cybernews import (
    parse_hackmanac_cybernews,
    intermediate_to_hackmanac_cybernews_leakrecord,
)
from .telegram_venarix import (
    parse_venarix,
    intermediate_to_venarix_leakrecord,
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


def run_RansomFeedNews_demo() -> None:
    """
    RansomFeedNews 채널에서 온 메시지를 예시로 사용하는 데모.

    실제 텔레그램 API 연동 없이,
    '이런 형식의 텍스트가 왔다'고 가정하고 파이프라인을 테스트한다.
    """
    raw_message = """
ID: 27781 
⚠️ Sun, 07 Dec 2025 14:42:25 CET 
🥷 sinobi 
🎯 Quality Companies, USA 
🔗 http://www.ransomfeed.it/index.php?page=post_details&id_post=27781
    """.strip()

    # 1) raw → IntermediateEvent
    event = parse_RansomFeedNews(
        raw_text=raw_message,
        message_id=123,  # 데모용 임의 값
        message_url="https://t.me/RansomFeedNews/123",
    )

    # group / victim 둘 다 없으면 의미 없는 메시지로 간주
    if not event.group_name and not event.victim_name:
        print("[SKIP] RansomFeedNews event without group/victim")
        return

    # 2) IntermediateEvent → LeakRecord
    record: LeakRecord = intermediate_to_RansomFeedNews_leakrecord(event)
    print(record)
    # 3) 공통 파이프라인 태우기
    process_leak_record(record)


# ---------------------------------------------------------------------------
# 3. ctifeeds 전용 데모
# ---------------------------------------------------------------------------


def run_ctifeeds_demo() -> None:
    """
    ctifeeds 채널에서 온 메시지를 예시로 사용하는 데모.

    실제 텔레그램 API 연동 없이,
    '이런 형식의 텍스트가 왔다'고 가정하고 파이프라인을 테스트한다.
    """
    raw_message = """

    """.strip()

    # 1) raw → IntermediateEvent
    event = parse_ctifeeds(
        raw_text=raw_message,
        message_id=123,  # 데모용 임의 값
        message_url="https://t.me/ctifeeds/123",
    )

    # group / victim 둘 다 없으면 의미 없는 메시지로 간주
    if not event.group_name and not event.victim_name:
        print("[SKIP] ctifeeds event without group/victim")
        return

    # 2) IntermediateEvent → LeakRecord
    record: LeakRecord = intermediate_to_ctifeeds_leakrecord(event)

    # 3) 공통 파이프라인 태우기
    process_leak_record(record)


# ---------------------------------------------------------------------------
# 4. hackmanac_cybernews 전용 데모
# ---------------------------------------------------------------------------


def run_hackmanac_cybernews_demo() -> None:
    """
    hackmanac_cybernews 채널에서 온 메시지를 예시로 사용하는 데모.

    실제 텔레그램 API 연동 없이,
    '이런 형식의 텍스트가 왔다'고 가정하고 파이프라인을 테스트한다.
    """
    raw_message = """
🚨Cyberattack Alert ‼️

🇺🇸USA - Scientology

Qilin hacking group claims to have breached Scientology.

Sector: Organizations
Threat class: Cybercrime
Observed: Dec 4, 2025
Status: Pending verification

—
About this post:
Hackmanac provides early warning and cyber situational awareness through its social channels. This alert is based on publicly available information that our analysts retrieved from clear and dark web sources. No confidential or proprietary data was downloaded, copied, or redistributed, and sensitive details were redacted from the attached screenshot(s).

For more details about this incident, our ESIX impact score, and additional context, visit HackRisk.io.
    """.strip()

    # 1) raw → IntermediateEvent
    event = parse_hackmanac_cybernews(
        raw_text=raw_message,
        message_id=123,  # 데모용 임의 값
        message_url="https://t.me/hackmanac_cybernews/123",
    )

    # group / victim 둘 다 없으면 의미 없는 메시지로 간주
    if not event.group_name and not event.victim_name:
        print("[SKIP] hackmanac_cybernews event without group/victim")
        return

    # 2) IntermediateEvent → LeakRecord
    record: LeakRecord = intermediate_to_hackmanac_cybernews_leakrecord(event)
    print(record)
    # 3) 공통 파이프라인 태우기
    process_leak_record(record)


# ---------------------------------------------------------------------------
# 5. venarix 전용 데모
# ---------------------------------------------------------------------------


def run_venarix_demo() -> None:
    """
    venarix 채널에서 온 메시지를 예시로 사용하는 데모.

    실제 텔레그램 API 연동 없이,
    '이런 형식의 텍스트가 왔다'고 가정하고 파이프라인을 테스트한다.
    """
    raw_message = """

    """.strip()

    # 1) raw → IntermediateEvent
    event = parse_venarix(
        raw_text=raw_message,
        message_id=123,  # 데모용 임의 값
        message_url="https://t.me/venarix/123",
    )

    # group / victim 둘 다 없으면 의미 없는 메시지로 간주
    if not event.group_name and not event.victim_name:
        print("[SKIP] venarix event without group/victim")
        return

    # 2) IntermediateEvent → LeakRecord
    record: LeakRecord = intermediate_venarix_to_leakrecord(event)

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
    # run_RansomFeedNews_demo()

    # 3) ctifeeds 채널 포맷 테스트
    # run_ctifeeds_demo()

    # 4) hackmanac_cybernews 채널 포맷 테스트
    run_hackmanac_cybernews_demo()

    # 5) venarix 채널 포맷 테스트
    # run_venarix_demo()

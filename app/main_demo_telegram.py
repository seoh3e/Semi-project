# app/main_demo_telegram.py

"""
텔레그램 기반 피드들을 '샘플 메시지'로 테스트하기 위한 데모 스크립트.

- 공통 처리 흐름:
    raw 텍스트              →  (채널별 parser)
    IntermediateEvent       →  LeakRecord
    LeakRecord              →  저장 + 알림

- 현재 구현된 채널:
    - generic 텔레그램 포맷 (DarkForum 스타일)
    - RansomFeedNews
    - ctifeeds
    - hackmanac_cybernews
    - venarix
"""

from __future__ import annotations

from .models import LeakRecord
from .parser import parse_telegram_message
from .storage import add_leak_record, append_leak_record_csv
from .notifier import notify_all

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


# ---------------------------------------------------------------------------
# 공통 처리 유틸
# ---------------------------------------------------------------------------

def process_leak_record(record: LeakRecord) -> None:
    """
    LeakRecord를 공동 파이프라인에 태우는 함수.
    - JSON 저장
    - CSV 저장 (대시보드용)
    - 콘솔 + Slack 알림
    """
    # 1) JSON 저장
    add_leak_record(record)

    # 2) CSV에도 한 줄 append (대시보드용)
    append_leak_record_csv(record)
    print("✅ CSV 저장 완료: data/leak_records.csv")

    # 3) 알림 (콘솔 + Slack)
    notify_all(record)


# ---------------------------------------------------------------------------
# 1) 일반 텔레그램 메시지 데모 (DarkForum 같은 포맷)
# ---------------------------------------------------------------------------

def run_generic_telegram_demo() -> None:
    raw_message = """
[DarkForum B] KR gov users leaked 2025

target service : Example Korean Gov Portal (gov-example.go.kr)
LEAK TYPES : email / password_hash / address
volume : 20,000
CONFIDENCE : HIGH
""".strip()

    record: LeakRecord = parse_telegram_message(raw_message)
    process_leak_record(record)


# ---------------------------------------------------------------------------
# 2) RansomFeedNews 전용 데모
# ---------------------------------------------------------------------------

def run_RansomFeedNews_demo() -> None:
    raw_message = """
ID: 27781 
⚠️Sun, 07 Dec 2025 14:42:25 CET 
🥷 sinobi 
🎯 Quality Companies, USA 
🔗 http://www.ransomfeed.it/index.php?page=post_details&id_post=27781
""".strip()

    event = parse_RansomFeedNews(
        raw_text=raw_message,
        message_id=123,
        message_url="https://t.me/RansomFeedNews/123",
    )

    if not event.group_name and not event.victim_name:
        print("[SKIP] RansomFeedNews event without group/victim")
        return

    record: LeakRecord = ransomfeed_to_leakrecord(event)
    process_leak_record(record)


# ---------------------------------------------------------------------------
# 3) ctifeeds 전용 데모
# ---------------------------------------------------------------------------

def run_ctifeeds_demo() -> None:
    raw_message = """
Recent defacement reported by Hax.or: http://psb.mikenongomulyo.sch.id http://psb.mikenongomulyo.sch.id
""".strip()

    event = parse_ctifeeds(
        raw_text=raw_message,
        message_id=124,
        message_url="https://t.me/ctifeeds/124",
    )

    if not event.group_name and not event.victim_name:
        print("[SKIP] ctifeeds event without group/victim")
        return

    record: LeakRecord = ctifeeds_to_leakrecord(event)
    process_leak_record(record)


# ---------------------------------------------------------------------------
# 4) hackmanac_cybernews 전용 데모
# ---------------------------------------------------------------------------

def run_hackmanac_cybernews_demo() -> None:
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

    event = parse_hackmanac_cybernews(
        raw_text=raw_message,
        message_id=125,
        message_url="https://t.me/hackmanac_cybernews/125",
    )

    if not event.group_name and not event.victim_name:
        print("[SKIP] hackmanac_cybernews event without group/victim")
        return

    record: LeakRecord = hackmanac_to_leakrecord(event)
    process_leak_record(record)


# ---------------------------------------------------------------------------
# 5) venarix 전용 데모
# ---------------------------------------------------------------------------

def run_venarix_demo() -> None:
    raw_message = """
🚨 New cyber event 🚨

Threat group: coinbasecartel

Victim: Acu Trans Solutions

For datailed insights on this incident, sign up for free at https://www.venarix.com
""".strip()

    event = parse_venarix(
        raw_text=raw_message,
        message_id=126,
        message_url="https://t.me/venarix/126",
    )

    if not event.group_name and not event.victim_name:
        print("[SKIP] venarix event without group/victim")
        return

    record: LeakRecord = venarix_to_leakrecord(event)
    process_leak_record(record)


if __name__ == "__main__":
    print("Use run_all_demos.py to run all demos.")

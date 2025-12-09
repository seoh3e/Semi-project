from datetime import date
from .models import LeakRecord
from .storage import add_leak_record
from .notifier import notify_new_leak


def run_demo() -> None:
    """
    다크웹 탐지팀이 유출 정보를 1건 발견했다고 가정하고,
    예시 데이터를 입력하는 데모 함수.
    """

    record = LeakRecord(
        collected_at=date.today(),
        source="DarkForum A",
        post_title="KR education site users dump 2024",
        post_id="DF-2024-TEST",
        author="leaker007",
        posted_at=date(2024, 11, 30),

        leak_types=["email", "password_hash", "phone"],
        estimated_volume=15000,
        file_formats=["sql", "zip"],

        target_service="Example Korean Education Service",
        domains=["edu-example.co.kr"],
        country="KR",

        threat_claim="2024년 10월 기준 최신 사용자 DB 1.5만 건 덤프",
        deal_terms="150 USD in BTC, 샘플 데이터 제공",
        confidence="high",

        screenshot_refs=["SS_2025-12-02_01.png"],
        osint_seeds={
            "email_patterns": ["*@edu-example.co.kr"],
            "domains": ["edu-example.co.kr"],
            "usernames": ["sample_user01", "teacher_test"],
        },
    )

    # 1) 저장
    add_leak_record(record)

    # 2) 알림
    notify_new_leak(record)


if __name__ == "__main__":
    # 패키지로 실행할 것이기 때문에, 터미널에서:
    #   python -m app.main_demo
    # 로 실행하는 걸 추천.
    run_demo()

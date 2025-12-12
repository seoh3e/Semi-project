# app/telegram_RansomFeedNews.py

from datetime import date, datetime
from typing import List
from urllib.parse import urlparse

from .models import IntermediateEvent, LeakRecord


# ─────────────────────────────────────────────
# URL 리스트 → 도메인 리스트 추출 (로컬 헬퍼)
# ─────────────────────────────────────────────


def _extract_domains(urls: List[str]) -> List[str]:
    """
    URL 리스트에서 도메인만 추출하여 중복 제거한 리스트를 반환한다.
    예:
        ["https://example.com/a", "http://sub.example.com", "https://example.com/b"]
        -> ["example.com", "sub.example.com"]
    """
    domains: List[str] = []

    for u in urls:
        try:
            netloc = urlparse(u).netloc.lower()
        except Exception:
            continue

        if netloc and netloc not in domains:
            domains.append(netloc)

    return domains


# ─────────────────────────────────────────────
# 1) raw_text → IntermediateEvent
# ─────────────────────────────────────────────


def parse_RansomFeedNews(
    raw_text: str, message_id=None, message_url=None
) -> IntermediateEvent:
    """
    RansomFeedNews 채널 메시지 파서.
    """

    lines = raw_text.splitlines()

    # 기본 포맷 예시:
    # ID: 27781
    # ⚠️ Sun, 07 Dec 2025 14:42:25 CET
    # 🥷 sinobi
    # 🎯 Quality Companies, USA
    # 🔗 http://www.ransomfeed.it/index.php?page=post_details&id_post=27781

    # 1) 두 번째 줄(raw 날짜 줄) 정리
    raw_line = lines[1].strip()

    # 앞에 붙은 이모지(⚠️, 📅 등) 제거
    # 알파벳이 시작될 때까지 앞부분을 잘라낸다.
    while raw_line and not raw_line[0].isalpha():
        raw_line = raw_line[1:].lstrip()

    # 2) 끝에 붙은 타임존(UTC, CET, GMT 등) 제거
    parts = raw_line.split()
    if parts and parts[-1].isupper():
        # 마지막 토큰이 전부 대문자면 타임존으로 보고 제거
        raw_line = " ".join(parts[:-1])

    # 이제 raw_line은 "Sun, 07 Dec 2025 14:42:25" 형태가 됨
    published_date_text = datetime.strptime(
        raw_line, "%a, %d %b %Y %H:%M:%S"
    ).date()

    # 3) 공격 그룹 / 피해자 / URL
    group = lines[2][2:-1]            # "🥷 sinobi" → "sinobi"
    victim = lines[3][2:-1]           # "🎯 Quality Companies, USA" → "Quality Companies, USA"
    urls: List[str] = [lines[4][2:]]  # "🔗 http://..." → "http://..."

    return IntermediateEvent(
        source_channel="@RansomFeedNews",
        raw_text=raw_text,
        message_id=message_id,
        message_url=message_url,
        group_name=group,
        victim_name=victim,
        published_at_text=published_date_text,
        urls=urls,
        tags=[],
    )


# ─────────────────────────────────────────────
# 2) IntermediateEvent → LeakRecord 변환기
# ─────────────────────────────────────────────


def intermediate_to_leakrecord(event: IntermediateEvent) -> LeakRecord:
    """
    파싱된 IntermediateEvent → LeakRecord 표준 구조 변환
    """

    # URL 리스트에서 도메인만 추출
    domains = _extract_domains(event.urls)

    return LeakRecord(
        collected_at=date.today(),
        source=event.source_channel,
        post_title=f"{event.group_name or ''} → {event.victim_name or ''}",
        post_id=str(event.message_id) if event.message_id else "",
        author=None,
        posted_at=event.published_at_text,
        leak_types=[],
        estimated_volume=None,
        file_formats=[],
        target_service=event.victim_name,
        domains=domains,
        country=None,
        threat_claim=event.group_name,
        deal_terms=None,
        confidence="medium",
        screenshot_refs=[],
        osint_seeds={"urls": event.urls},
    )

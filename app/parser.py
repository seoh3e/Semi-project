# app/parser.py
from datetime import date
from typing import List
import re

from .models import LeakRecord


def parse_telegram_message(raw: str) -> LeakRecord:
    """
    텔레그램 피드에서 온 메시지 한 개(raw text)를
    LeakRecord 객체로 변환하는 간단한 파서.

    ⚠️ 실제 피드 형식에 맞춰서 regex 부분만 나중에 조정하면 됨.
    """

    # 기본값(혹시 못 뽑은 필드는 None / 빈값으로 둔다)
    source = "Telegram Feed"
    post_title = ""
    target_service = ""
    domains: List[str] = []
    leak_types: List[str] = []
    estimated_volume = None
    confidence = "unknown"

    # 예시 포맷(팀이 정해서 맞추면 됨):
    # [DarkForum A] KR education site users dump 2024
    # Target: Example Korean Education Service (edu-example.co.kr)
    # Leak: email, password_hash, phone
    # Volume: 15000
    # Confidence: high

    # 1) 첫 줄: [Source] Title
    # ---------------------------------
    first_line = raw.splitlines()[0].strip() if raw.splitlines() else ""
    m = re.match(r"\[(?P<source>.+?)\]\s*(?P<title>.+)", first_line)
    if m:
        source = m.group("source").strip()
        post_title = m.group("title").strip()
    else:
        # 대괄호 형식이 아니어도, 일단 전체를 제목으로
        post_title = first_line

    # 2) Target 서비스 / 도메인
    # ---------------------------------
    m = re.search(
        r"Target\s*:\s*(?P<service>.+?)(\((?P<domain>[^)]+)\))?",
        raw,
        re.IGNORECASE,
    )
    if m:
        target_service = m.group("service").strip()
        if m.group("domain"):
            domains = [m.group("domain").strip()]

    # 3) Leak 타입들 (쉼표/슬래시 기준 분리)
    # ---------------------------------
    m = re.search(r"Leak\s*:\s*(?P<leaks>.+)", raw, re.IGNORECASE)
    if m:
        leak_raw = m.group("leaks")
        leak_types = [t.strip() for t in re.split(r"[,/]", leak_raw) if t.strip()]

    # 4) Volume (숫자만 추출)
    # ---------------------------------
    m = re.search(r"Volume\s*:\s*(?P<vol>[\d,]+)", raw, re.IGNORECASE)
    if m:
        vol_str = m.group("vol").replace(",", "")
        try:
            estimated_volume = int(vol_str)
        except ValueError:
            estimated_volume = None

    # 5) Confidence
    # ---------------------------------
    m = re.search(r"Confidence\s*:\s*(?P<conf>\w+)", raw, re.IGNORECASE)
    if m:
        confidence = m.group("conf").lower()

    # 6) LeakRecord로 변환
    # ---------------------------------
    record = LeakRecord(
        collected_at=date.today(),
        source=source,
        post_title=post_title,
        post_id=None,              # 텔레그램 메시지 ID를 나중에 연결 가능
        author=None,               # 필요하면 feed 쪽에서 넘겨주기
        posted_at=None,            # 메시지 timestamp 사용 가능

        leak_types=leak_types,
        estimated_volume=estimated_volume,
        file_formats=[],           # 필요하면 추후 패턴 추가
        target_service=target_service,
        domains=domains,
        country=None,

        threat_claim=None,
        deal_terms=None,
        confidence=confidence,
        screenshot_refs=[],
        osint_seeds={
            "raw_message": raw,
        },
    )

    return record

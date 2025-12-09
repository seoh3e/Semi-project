# app/parser.py
from datetime import date
from typing import List
import re

from .models import LeakRecord

# ---- 재사용할 정규식 패턴들 ----

# [DarkForum A] KR education site users dump 2024
SOURCE_TITLE_RE = re.compile(
    r"^\s*\[(?P<source>[^\]\-]+)\]\s*[:\-]?\s*(?P<title>.+)$",
    re.IGNORECASE,
)

# Target / Target Service / Service / Victim 라인
# 예: Target: Example Service (edu-example.co.kr)
TARGET_RE = re.compile(
    r"^(target|target service|service|victim)\s*[:\-]\s*(?P<service>.+?)(?:\s*\((?P<domain>[^)]+)\))?\s*$",
    re.IGNORECASE,
)

# Domains: aaa.com / bbb.net, ccc.org
DOMAINS_RE = re.compile(
    r"^(domains?)\s*[:\-]\s*(?P<domains>.+)$",
    re.IGNORECASE,
)

# Leak: email, password_hash, phone
LEAK_RE = re.compile(
    r"^(leak|leak types?)\s*[:\-]\s*(?P<leaks>.+)$",
    re.IGNORECASE,
)

# Volume: 15000
VOLUME_RE = re.compile(
    r"^volume\s*[:\-]\s*(?P<vol>[\d,\.]+)",
    re.IGNORECASE,
)

# Confidence: high
CONF_RE = re.compile(
    r"^confidence\s*[:\-]\s*(?P<conf>.+)$",
    re.IGNORECASE,
)

# 본문 어딘가에 숨어 있는 도메인 후보 찾기용 (fallback)
DOMAIN_FALLBACK_RE = re.compile(
    r"\b(?P<domain>[\w\.-]+\.(?:com|net|org|co\.kr|go\.kr|kr))\b",
    re.IGNORECASE,
)


def normalize_confidence(conf_raw: str) -> str:
    """
    다양한 표현을 high/medium/low/unknown 으로 정규화
    """
    if not conf_raw:
        return "unknown"

    c = conf_raw.lower().strip()

    # 정확 매칭 우선
    if c in ("high", "medium", "low"):
        return c

    # 포함 관계 기반 대충 매핑
    if any(k in c for k in ["very high", "strong", "certain", "confidence: high"]):
        return "high"
    if any(k in c for k in ["likely", "probably", "medium"]):
        return "medium"
    if any(k in c for k in ["low", "weak"]):
        return "low"

    return "unknown"



def parse_telegram_message(raw: str) -> LeakRecord:
    """
    텔레그램 피드에서 온 메시지 한 개(raw text)를
    LeakRecord 객체로 변환하는 정교화 버전 파서.
    """

    # 기본값(혹시 못 뽑으면 이 값 사용)
    source = "Telegram Feed"
    post_title = ""
    target_service = ""
    domains: List[str] = []
    leak_types: List[str] = []
    estimated_volume = None
    confidence = "unknown"

    # fallback 으로 모아둘 도메인 후보들
    domain_candidates: List[str] = []

    # 줄 단위로 정리 (공백 줄 제거)
    lines = [line.strip() for line in raw.splitlines() if line.strip()]

    # 1) 첫 줄에서 source / title 추출 시도
    if lines:
        m = SOURCE_TITLE_RE.match(lines[0])
        if m:
            source = m.group("source").strip()
            post_title = m.group("title").strip()
        else:
            # 대괄호/대시 형식이 아니면 그냥 전체를 제목으로 사용
            post_title = lines[0]

    # 2) 나머지 줄 돌면서 Target / Leak / Volume / Confidence / Domains 찾기
    for line in lines[1:]:
        # Target / Service / Victim
        m = TARGET_RE.match(line)
        if m:
            target_service = m.group("service").strip()

            domain_text = m.group("domain")
            if domain_text:
                # 괄호 안에 여러 도메인이 있을 수 있으니 / , 로 분리
                for d in re.split(r"[\/,]", domain_text):
                    d_clean = d.strip()
                    if d_clean:
                        domain_candidates.append(d_clean)
            continue

        # Domains: aaa.com / bbb.net, ccc.org
        m = DOMAINS_RE.match(line)
        if m:
            domains_text = m.group("domains")
            for d in re.split(r"[\/,]", domains_text):
                d_clean = d.strip()
                if d_clean:
                    domain_candidates.append(d_clean)
            continue

        # Leak types
        m = LEAK_RE.match(line)
        if m:
            leak_raw = m.group("leaks")
            # 쉼표, 슬래시 둘 다 구분자로 허용
            leak_types = [
                t.strip()
                for t in re.split(r"[,/]", leak_raw)
                if t.strip()
            ]
            continue

        # Volume
        m = VOLUME_RE.match(line)
        if m:
            vol_str = m.group("vol").replace(",", "").replace(".", "")
            try:
                estimated_volume = int(vol_str)
            except ValueError:
                estimated_volume = None
            continue

        # Confidence
        m = CONF_RE.match(line)
        if m:
            confidence = normalize_confidence(m.group("conf"))
            continue

        # 위 어떤 라벨에도 안 걸렸다면, 본문에 숨어 있는 도메인 fallback 검색
        for match in DOMAIN_FALLBACK_RE.finditer(line):
            d_clean = match.group("domain").strip()
            if d_clean:
                domain_candidates.append(d_clean)

    # 3) 도메인 후보들 정제 & 중복 제거
    if domain_candidates and not domains:
        seen = set()
        for d in domain_candidates:
            if d not in seen:
                seen.add(d)
                domains.append(d)

    # 4) LeakRecord로 변환
    record = LeakRecord(
        collected_at=date.today(),
        source=source,
        post_title=post_title,
        post_id=None,
        author=None,
        posted_at=None,

        leak_types=leak_types,
        estimated_volume=estimated_volume,
        file_formats=[],
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
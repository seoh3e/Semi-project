from dataclasses import dataclass, field
from datetime import date
from typing import List, Dict, Optional


@dataclass
class IntermediateEvent:
    source_channel: str
    raw_text: str

    message_id: Optional[int] = None
    message_url: Optional[str] = None

    group_name: Optional[str] = None
    victim_name: Optional[str] = None

    # RansomFeedNews 템플릿 호환용
    published_at_text: Optional[str] = None

    urls: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


@dataclass
class LeakRecord:
    collected_at: date               # 수집일
    source: str                      # 출처(포럼/마켓 이름)
    post_title: str                  # 게시글 제목
    post_id: str                     # 게시글 ID 또는 링크 일부
    author: Optional[str]            # 작성자 닉네임
    posted_at: Optional[date]        # 게시 날짜

    leak_types: List[str]            # ["email", "password_hash", ...]
    estimated_volume: Optional[int]  # 추정 건수
    file_formats: List[str]          # ["csv", "sql", "zip", ...]

    target_service: Optional[str]    # 서비스/조직명
    domains: List[str]               # ["example.com", ...]
    country: Optional[str]           # "KR", "US" 등

    threat_claim: Optional[str]      # 공격자 주장
    deal_terms: Optional[str]        # 거래 조건
    confidence: str                  # "low" / "medium" / "high"

    screenshot_refs: List[str] = field(default_factory=list)
    osint_seeds: Dict = field(default_factory=dict)

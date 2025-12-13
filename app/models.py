from dataclasses import dataclass, field, asdict
from datetime import date
from typing import List, Dict, Optional, Any


# =============================================================================
# LeakRecord schema constants (storage/summary/dashboard에서 공통으로 쓰기)
# =============================================================================

LEAKRECORD_REQUIRED_FIELDS = [
    "collected_at",
    "source",
    "post_title",
    "post_id",
    "posted_at",
    "leak_types",
    "domains",
    "confidence",
]

LEAKRECORD_ALL_FIELDS = [
    "collected_at",         # date
    "source",               # str
    "post_title",           # str
    "post_id",              # str
    "author",               # Optional[str]
    "posted_at",            # Optional[date]
    "leak_types",           # List[str]
    "estimated_volume",     # Optional[int]
    "file_formats",         # List[str]
    "target_service",       # Optional[str]
    "domains",              # List[str]
    "country",              # Optional[str]
    "threat_claim",         # Optional[str]
    "deal_terms",           # Optional[str]
    "confidence",           # str
    "screenshot_refs",      # List[str]
    "osint_seeds",          # Dict[str, Any]

    # storage/dashboard에서 쓰는 확장 필드(없어도 되지만, 있으면 “누락”이 사라짐)
    "message_url",          # Optional[str]
]


# =============================================================================
# IntermediateEvent (채널별 파서 output)
# =============================================================================

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


# =============================================================================
# LeakRecord (표준 스키마)
# =============================================================================

@dataclass
class LeakRecord:
    collected_at: date = field(default_factory=date.today)   # 수집일 (기본: 오늘)
    source: str = ""                                         # 출처(포럼/마켓/채널)
    post_title: str = ""                                     # 게시글 제목
    post_id: str = ""                                        # 게시글 ID 또는 링크 일부
    author: Optional[str] = None                             # 작성자 닉네임
    posted_at: Optional[date] = None                         # 게시 날짜

    # 리스트/딕셔너리 필드는 반드시 default_factory로!
    leak_types: List[str] = field(default_factory=lambda: ["unknown"])  # ["email", ...]
    estimated_volume: Optional[int] = None                               # 추정 건수
    file_formats: List[str] = field(default_factory=list)               # ["csv", ...]
    target_service: Optional[str] = None                                 # 서비스/조직명
    domains: List[str] = field(default_factory=list)                     # ["example.com", ...]
    country: Optional[str] = None                                        # "KR", "US" 등

    threat_claim: Optional[str] = None      # 공격자 주장
    deal_terms: Optional[str] = None        # 거래 조건
    confidence: str = "medium"              # "low" / "medium" / "high"

    screenshot_refs: List[str] = field(default_factory=list)
    osint_seeds: Dict[str, Any] = field(default_factory=dict)

    # dashboard/storage에서 필요(없으면 빈 값으로 유지)
    message_url: Optional[str] = None

    def normalize(self) -> "LeakRecord":
        """
        저장/요약/대시보드 전에 호출하여 “키는 항상 존재 + 값은 표준화” 상태로 만든다.
        - leak_types/domains/file_formats 등의 리스트 정리
        - leak_types 비면 ['unknown']
        - confidence 비면 'medium'
        - None이 들어온 문자열 필드는 ''로 보정(가능한 범위)
        """

        # 리스트류: None 방지 + 빈 값 제거 + 중복 제거 + (선택) 소문자 정규화
        self.leak_types = [x for x in (self.leak_types or []) if x]
        if not self.leak_types:
            self.leak_types = ["unknown"]
        else:
            self.leak_types = sorted(set([t.lower() for t in self.leak_types]))

        self.domains = sorted(set([d.lower() for d in (self.domains or []) if d]))
        self.file_formats = sorted(set([f.lower() for f in (self.file_formats or []) if f]))
        self.screenshot_refs = sorted(set([s for s in (self.screenshot_refs or []) if s]))

        # confidence 기본값
        if not self.confidence:
            self.confidence = "medium"

        # 문자열 필드: None이면 빈 문자열로(필수 성격 필드 위주)
        if self.source is None:
            self.source = ""
        if self.post_title is None:
            self.post_title = ""
        if self.post_id is None:
            self.post_id = ""

        # dict 기본값
        if self.osint_seeds is None:
            self.osint_seeds = {}

        # 날짜 기본값(혹시 None이면)
        if self.collected_at is None:
            self.collected_at = date.today()

        return self

    def to_dict(self) -> Dict[str, Any]:
        """
        dataclass → dict 변환.
        storage.py에서 ensure_schema_dict로 한 번 더 키 보정하지만,
        여기서도 기본 dict를 확실히 제공한다.
        """
        return asdict(self)

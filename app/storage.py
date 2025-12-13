# app/storage.py

from datetime import date, datetime
from dataclasses import is_dataclass, asdict
from pathlib import Path
from typing import List, Any, Dict
import csv
import json
import os

from .models import LeakRecord, LEAKRECORD_ALL_FIELDS


# =============================================================================
# 공통 경로 설정
# =============================================================================

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# JSON 저장용 (전체 LeakRecord 백업 / 디버깅용)
# => leak_summary.json과 구분하기 위해 파일명을 leaks.json으로 사용
JSON_PATH = DATA_DIR / "leaks.json"

# 대시보드에서 읽을 CSV 경로 (append 용)
CSV_RECORDS_PATH = DATA_DIR / "leak_records.csv"

# 대시보드에서 사용하는 CSV 컬럼 정의 (고정)
CSV_HEADER = [
    "source",
    "post_title",
    "target_service",
    "domains",
    "leak_types",
    "estimated_volume",
    "confidence",
    "collected_at",
    "post_id",
    "message_url",
]

# summary 파일(매번 새로 생성)에서 사용하는 헤더(고정)
SUMMARY_HEADER = [
    "post_title",
    "post_id",
    "author",
    "source",
    "posted_at",
    "collected_at",
    "leak_types",
    "estimated_volume",
    "file_formats",
    "target_service",
    "domains",
    "country",
    "threat_claim",
    "deal_terms",
    "confidence",
]


# =============================================================================
# 공통 유틸
# =============================================================================

def _to_iso(v: Any) -> Any:
    """date/datetime이면 isoformat으로 직렬화해 반환."""
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


def normalize_record(record: LeakRecord) -> LeakRecord:
    """
    저장 직전에 normalize()를 강제한다.
    (models.py에서 normalize()를 구현했을 때 가장 효과가 큼)
    """
    if hasattr(record, "normalize") and callable(getattr(record, "normalize")):
        return record.normalize()
    return record


def ensure_schema_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """
    LeakRecord 저장용 dict에서 키/컬럼 누락을 방지한다.
    - LEAKRECORD_ALL_FIELDS 기준으로 키를 강제 생성
    - storage 레벨에서만 필요한 message_url도 추가 보정
    """
    # LeakRecord 전체 필드 + storage에서 쓰는 확장 필드
    all_fields = list(LEAKRECORD_ALL_FIELDS)
    if "message_url" not in all_fields:
        all_fields.append("message_url")

    list_fields = {"leak_types", "file_formats", "domains", "screenshot_refs", "urls"}
    none_fields = {"author", "posted_at", "estimated_volume", "target_service", "country",
                   "threat_claim", "deal_terms"}

    for k in all_fields:
        if k not in d:
            if k in list_fields:
                d[k] = []
            elif k in none_fields:
                d[k] = None
            else:
                d[k] = ""

    # 최소 규칙(대시보드/필터 안정화)
    if not d.get("leak_types"):
        d["leak_types"] = ["unknown"]
    if not d.get("confidence"):
        d["confidence"] = "medium"

    # date/datetime 직렬화(중첩 구조는 storage에서 필요 시 확장)
    for k, v in list(d.items()):
        d[k] = _to_iso(v)

    return d


# =============================================================================
# LeakRecord → dict 변환 유틸 (dataclass / pydantic 모두 대응)
# =============================================================================

def record_to_dict(record: LeakRecord) -> dict:
    """LeakRecord 객체를 평범한 dict로 변환한다. (저장 직전 normalize + 스키마 보정 포함)"""

    record = normalize_record(record)

    # pydantic v2
    if hasattr(record, "model_dump"):
        d = record.model_dump()
        return ensure_schema_dict(d)

    # pydantic v1
    if hasattr(record, "dict"):
        d = record.dict()
        return ensure_schema_dict(d)

    # dataclass 인 경우
    if is_dataclass(record):
        d = asdict(record)
        return ensure_schema_dict(d)

    # 그 외에는 __dict__ 사용
    d = {k: v for k, v in record.__dict__.items() if not k.startswith("_")}
    return ensure_schema_dict(d)


# =============================================================================
# (옵션) 중복 저장 방지 – post_id 기준
# =============================================================================

def is_duplicate_record(record: LeakRecord) -> bool:
    """
    CSV에 이미 동일한 post_id가 있으면 True.
    post_id가 없으면 그냥 False 반환.
    """
    post_id = getattr(record, "post_id", None)
    if not post_id:
        return False

    if not CSV_RECORDS_PATH.exists():
        return False

    with CSV_RECORDS_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("post_id") == str(post_id):
                return True

    return False


# =============================================================================
# 1) JSON 저장 (기존 add_leak_record 기능)
# =============================================================================

def add_leak_record(record: LeakRecord) -> None:
    """LeakRecord를 JSON 파일에 누적 저장한다."""
    file_path = JSON_PATH

    # 기존 데이터 불러오기
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                items = json.load(f)
            except json.JSONDecodeError:
                items = []
    else:
        items = []

    # 새 record 추가 (normalize + dict + schema 보정 포함)
    items.append(record_to_dict(record))

    # 다시 저장
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2, default=str)


# =============================================================================
# 2) CSV 저장 – 대시보드용 한 레코드씩 append
# =============================================================================

def append_leak_record_csv(record: LeakRecord) -> None:
    """
    LeakRecord를 data/leak_records.csv에 한 줄씩 append한다.
    파일이 없으면 헤더를 먼저 쓴다.
    """

    # (옵션) 중복이면 스킵
    if is_duplicate_record(record):
        print(f"[SKIP] duplicated post_id={record.post_id}")
        return

    # ✅ 저장 직전 normalize + dict + 스키마 보정
    d = record_to_dict(record)

    file_exists = CSV_RECORDS_PATH.exists()

    with CSV_RECORDS_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # 처음 생성되는 파일이면 헤더 추가
        if not file_exists:
            writer.writerow(CSV_HEADER)

        # domains / leak_types는 리스트일 수 있으니 쉼표 join
        domains = d.get("domains") or []
        leak_types = d.get("leak_types") or []
        domains_str = ",".join(domains) if isinstance(domains, list) else str(domains)
        leak_types_str = ",".join(leak_types) if isinstance(leak_types, list) else str(leak_types)

        writer.writerow([
            d.get("source", ""),
            d.get("post_title", ""),
            d.get("target_service", "") or "",
            domains_str,
            leak_types_str,
            d.get("estimated_volume", "") if d.get("estimated_volume") is not None else "",
            d.get("confidence", "medium"),
            d.get("collected_at", ""),
            d.get("post_id", ""),
            d.get("message_url", "") or "",
        ])


# =============================================================================
# 3) 요약 파일용 변환/저장 함수 (leak_summary.csv / json)
# =============================================================================

def leakrecords_to_rows(records: List[LeakRecord]) -> List[dict]:
    rows: List[dict] = []

    for r in records:
        d = record_to_dict(r)  # ✅ normalize + schema 보정 포함

        row = {
            "post_title": d.get("post_title", ""),
            "post_id": d.get("post_id", ""),
            "author": d.get("author", "") or "",
            "source": d.get("source", ""),
            "posted_at": d.get("posted_at", "") or "",
            "collected_at": d.get("collected_at", "") or "",
            "leak_types": ", ".join(d.get("leak_types") or []),
            "estimated_volume": d.get("estimated_volume", "") if d.get("estimated_volume") is not None else "",
            "file_formats": ", ".join(d.get("file_formats") or []),
            "target_service": d.get("target_service", "") or "",
            "domains": ", ".join(d.get("domains") or []),
            "country": d.get("country", "") or "",
            "threat_claim": d.get("threat_claim", "") or "",
            "deal_terms": d.get("deal_terms", "") or "",
            "confidence": d.get("confidence", "medium"),
        }

        # ✅ 헤더 기준으로 누락 키 방지(혹시라도)
        rows.append({k: row.get(k, "") for k in SUMMARY_HEADER})

    return rows


def save_leak_summary(
    records: List[LeakRecord],
    csv_path: str = "data/leak_summary.csv",
    json_path: str = "data/leak_summary.json",
) -> None:
    """
    채널별 최근 N개의 LeakRecord를 모아서
    leak_summary.csv / leak_summary.json으로 한 번에 저장하는 함수.
    기존 append_leak_record_csv와는 다르게, 매번 '새 파일'을 생성한다.
    """
    if not records:
        print("[WARN] save_leak_summary: records가 비어 있어서 저장하지 않음.")
        return

    rows = leakrecords_to_rows(records)

    csv_p = Path(csv_path)
    csv_p.parent.mkdir(parents=True, exist_ok=True)

    # 요약 파일이므로 매번 덮어쓴다 (w 모드)
    with csv_p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_HEADER)
        writer.writeheader()
        writer.writerows(rows)

    # JSON 요약도 같은 rows 기준으로 저장
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(rows, jf, ensure_ascii=False, indent=2, default=str)

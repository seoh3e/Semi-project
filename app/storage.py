# app/storage.py

from datetime import date, datetime
from dataclasses import is_dataclass, asdict
from pathlib import Path
from typing import List
import csv
import json
import os

from .models import LeakRecord


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

# 대시보드에서 사용하는 CSV 컬럼 정의
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


# =============================================================================
# LeakRecord → dict 변환 유틸 (dataclass / pydantic 모두 대응)
# =============================================================================

def record_to_dict(record: LeakRecord) -> dict:
    """LeakRecord 객체를 평범한 dict로 변환한다."""

    # pydantic v2
    if hasattr(record, "model_dump"):
        return record.model_dump()

    # pydantic v1
    if hasattr(record, "dict"):
        return record.dict()

    # dataclass 인 경우
    if is_dataclass(record):
        return asdict(record)

    # 그 외에는 __dict__ 사용
    return {
        k: v
        for k, v in record.__dict__.items()
        if not k.startswith("_")
    }


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

    # 새 record 추가 (dict로 변환)
    items.append(record_to_dict(record))

    # 날짜/시간 직렬화용 converter
    def default_converter(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        raise TypeError(f"Type {type(o)} not serializable")

    # 다시 저장
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(
            items,
            f,
            ensure_ascii=False,
            indent=2,
            default=default_converter,
        )


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

    file_exists = CSV_RECORDS_PATH.exists()

    with CSV_RECORDS_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # 처음 생성되는 파일이면 헤더 추가
        if not file_exists:
            writer.writerow(CSV_HEADER)

        # domains / leak_types는 리스트일 수 있으니 쉼표 join
        domains_str = ",".join(record.domains) if getattr(record, "domains", None) else ""
        leak_types_str = ",".join(record.leak_types) if getattr(record, "leak_types", None) else ""

        writer.writerow([
            record.source,
            record.post_title,
            record.target_service or "",
            domains_str,
            leak_types_str,
            record.estimated_volume if record.estimated_volume is not None else "",
            record.confidence,
            record.collected_at,
            record.post_id,
            getattr(record, "message_url", ""),
        ])


# =============================================================================
# 3) 요약 파일용 변환/저장 함수 (leak_summary.csv / json)
# =============================================================================

def leakrecords_to_rows(records: List[LeakRecord]) -> list[dict]:
    rows: list[dict] = []
    for r in records:
        rows.append(
            {
                "post_title": r.post_title,
                "post_id": r.post_id,
                "author": r.author,
                "source": r.source,
                "posted_at": r.posted_at.isoformat() if r.posted_at else "",
                "collected_at": (
                    r.collected_at.isoformat()
                    if hasattr(r.collected_at, "isoformat")
                    else str(r.collected_at)
                ),
                "leak_types": ", ".join(r.leak_types),
                "estimated_volume": (
                    r.estimated_volume if r.estimated_volume is not None else ""
                ),
                "file_formats": ", ".join(r.file_formats),
                "target_service": r.target_service or "",
                "domains": ", ".join(r.domains),
                "country": r.country or "",
                "threat_claim": r.threat_claim or "",
                "deal_terms": r.deal_terms or "",
                "confidence": r.confidence,
            }
        )
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
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    # JSON 요약도 같은 rows 기준으로 저장
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(rows, jf, ensure_ascii=False, indent=2, default=str)

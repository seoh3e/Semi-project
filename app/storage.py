# app/storage.py

from datetime import date, datetime
import csv
import json
import os
from pathlib import Path
from dataclasses import is_dataclass, asdict

from .models import LeakRecord


# =============================================================================
# 공통 경로 설정
# =============================================================================

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# JSON 저장용 (백업 / 디버깅용)
JSON_PATH = DATA_DIR / "leak_summary.json"

# 대시보드에서 읽을 CSV 경로
CSV_RECORDS_PATH = DATA_DIR / "leak_records.csv"

# 대시보드에서 사용하는 CSV 컬럼 정의
CSV_HEADER = [
    "source",        # 채널 / feed 이름 (@RansomFeedNews 등)
    "title",         # 글 제목 또는 핵심 문구
    "target_service",# 피해 서비스 / 회사명
    "domains",       # 도메인 목록 (쉼표 join)
    "leak_types",    # 유출 타입 목록 (예: email, password 등)
    "volume",        # 유출 규모 (문자열/숫자 상관 없음)
    "confidence",    # 신뢰도 (low/medium/high)
    "collected_at",  # 수집일 (YYYY-MM-DD)
    "message_id",    # 텔레그램 메시지 ID
    "message_url",   # 텔레그램 메시지 URL
]


# =============================================================================
# LeakRecord → dict 변환 유틸 (dataclass / pydantic 모두 대응)
# =============================================================================

def record_to_dict(record: LeakRecord) -> dict:
    """LeakRecord 객체를 평범한 dict로 변환한다."""

    # pydantic v1 / v2 대응
    if hasattr(record, "model_dump"):
        return record.model_dump()
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
# (옵션) 중복 저장 방지 – message_id 기준
# =============================================================================

def is_duplicate_record(record: LeakRecord) -> bool:
    """
    CSV에 이미 동일한 message_id가 있으면 True.
    message_id가 없으면 그냥 False 반환.
    """
    msg_id = getattr(record, "message_id", None)
    if not msg_id:
        return False

    if not CSV_RECORDS_PATH.exists():
        return False

    with CSV_RECORDS_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("message_id") == str(msg_id):
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
        print(f"[SKIP] duplicated message_id={record.message_id}")
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
            getattr(record, "source", ""),
            getattr(record, "title", ""),
            getattr(record, "target_service", ""),
            domains_str,
            leak_types_str,
            getattr(record, "volume", ""),
            getattr(record, "confidence", ""),
            getattr(record, "collected_at", ""),
            getattr(record, "message_id", ""),
            getattr(record, "message_url", ""),
        ])

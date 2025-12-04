import csv
import json
import os
from datetime import date
from dataclasses import asdict
from typing import List
from .models import LeakRecord


DATA_DIR = "data"
CSV_PATH = os.path.join(DATA_DIR, "leak_summary.csv")
JSON_PATH = os.path.join(DATA_DIR, "leak_summary.json")

def is_duplicate(record: LeakRecord) -> bool:
    """
    CSV에 이미 같은 유출이 있는지 확인.
    - 기준: source + post_title 조합이 동일하면 같은 유출이라고 간주
    """

    # CSV가 아직 없으면 당연히 중복 아님
    if not os.path.exists(CSV_PATH):
        return False

    key = (
        (record.source or "").strip(),
        (record.post_title or "").strip(),
    )

    import csv

    with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_key = (
                (row.get("source") or "").strip(),
                (row.get("post_title") or "").strip(),
            )
            if row_key == key:
                # 이미 동일한 Source + Title 이 존재 → 중복
                return True

    return False


def _record_to_serializable_dict(r: LeakRecord) -> dict:
    """JSON으로 저장 가능하도록 date 타입을 문자열로 바꾸는 헬퍼."""
    d = asdict(r)
    d["collected_at"] = r.collected_at.isoformat()
    d["posted_at"] = r.posted_at.isoformat() if r.posted_at else None
    return d


def _dict_to_record(d: dict) -> LeakRecord:
    """JSON에서 읽어온 dict를 LeakRecord 객체로 변환."""
    collected_at = date.fromisoformat(d["collected_at"])
    posted_at = date.fromisoformat(d["posted_at"]) if d.get("posted_at") else None

    return LeakRecord(
        collected_at=collected_at,
        source=d["source"],
        post_title=d["post_title"],
        post_id=d["post_id"],
        author=d.get("author"),
        posted_at=posted_at,
        leak_types=d.get("leak_types", []),
        estimated_volume=d.get("estimated_volume"),
        file_formats=d.get("file_formats", []),
        target_service=d.get("target_service"),
        domains=d.get("domains", []),
        country=d.get("country"),
        threat_claim=d.get("threat_claim"),
        deal_terms=d.get("deal_terms"),
        confidence=d.get("confidence", "medium"),
        screenshot_refs=d.get("screenshot_refs", []),
        osint_seeds=d.get("osint_seeds", {}),
    )


# ---------------- CSV 저장 ----------------
def save_to_csv(records: List[LeakRecord], path: str = CSV_PATH) -> None:
    fieldnames = [
        "collected_at", "source", "post_title", "post_id", "author",
        "posted_at", "leak_types", "estimated_volume", "file_formats",
        "target_service", "domains", "country", "threat_claim",
        "deal_terms", "confidence", "screenshot_refs", "osint_seeds",
    ]

    os.makedirs(DATA_DIR, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for r in records:
            writer.writerow({
                "collected_at": r.collected_at.isoformat(),
                "source": r.source,
                "post_title": r.post_title,
                "post_id": r.post_id,
                "author": r.author or "",
                "posted_at": r.posted_at.isoformat() if r.posted_at else "",
                "leak_types": ", ".join(r.leak_types),
                "estimated_volume": r.estimated_volume if r.estimated_volume is not None else "",
                "file_formats": ", ".join(r.file_formats),
                "target_service": r.target_service or "",
                "domains": ", ".join(r.domains),
                "country": r.country or "",
                "threat_claim": r.threat_claim or "",
                "deal_terms": r.deal_terms or "",
                "confidence": r.confidence,
                "screenshot_refs": ", ".join(r.screenshot_refs),
                "osint_seeds": json.dumps(r.osint_seeds, ensure_ascii=False),
            })


# ---------------- JSON 저장 ----------------
def save_to_json(records: List[LeakRecord], path: str = JSON_PATH) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    data = [_record_to_serializable_dict(r) for r in records]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# ---------------- 한 건 추가 + 전체 저장 ----------------
def add_leak_record(record: LeakRecord) -> None:
    # 0) 중복 여부 먼저 확인
    if is_duplicate(record):
        print("[INFO] duplicate leak detected, skip saving.")
        return

    """
    새 유출 정보를 1건 추가할 때 호출.
    - 기존 JSON을 읽어서 리스트에 추가
    - JSON 전체 다시 저장
    - 그 리스트를 기준으로 CSV 전체 다시 저장
    """
    # 기존 데이터 읽기
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            raw_list = json.load(f)
    else:
        raw_list = []

    # 새 레코드 추가
    raw_list.append(_record_to_serializable_dict(record))

    # JSON 다시 저장
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(raw_list, f, indent=4, ensure_ascii=False)

    # LeakRecord 객체 리스트로 변환해서 CSV 저장
    records = [_dict_to_record(d) for d in raw_list]
    save_to_csv(records)

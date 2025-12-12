#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import csv
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple


DEFAULT_JSON = Path("data/leak_summary.json")
DEFAULT_CSV = Path("data/leak_summary.csv")


def _is_nonempty_str(x: Any) -> bool:
    return isinstance(x, str) and x.strip() != ""


def _is_nonempty_list(x: Any) -> bool:
    return isinstance(x, list) and len(x) > 0


def _get_urls(rec: Dict[str, Any]) -> List[str]:
    seeds = rec.get("osint_seeds") or {}
    urls = seeds.get("urls")
    if isinstance(urls, list):
        return [u for u in urls if _is_nonempty_str(u)]
    return []


def _normalize_source(rec: Dict[str, Any]) -> str:
    # "source"가 없을 수도 있으니 방어
    src = rec.get("source")
    if _is_nonempty_str(src):
        return src.strip()
    return "(unknown)"


def load_records_from_json(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    # 혹시 {"records":[...]} 형태면 대응
    if isinstance(data, dict) and isinstance(data.get("records"), list):
        return [r for r in data["records"] if isinstance(r, dict)]
    raise ValueError(f"Unexpected JSON shape in {path}")


def load_records_from_csv(path: Path) -> List[Dict[str, Any]]:
    # CSV는 구조가 다양할 수 있어서, 최소 컬럼 기반으로만 체크
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
    return records


def compute_coverage(records: List[Dict[str, Any]], mode: str) -> Dict[str, Dict[str, int]]:
    """
    mode:
      - "json": LeakRecord 원형 기반(추천)
      - "csv" : 저장된 문자열 기반(보조)
    """
    stats: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for rec in records:
        src = _normalize_source(rec)
        stats[src]["total"] += 1

        if mode == "json":
            # urls
            if len(_get_urls(rec)) > 0:
                stats[src]["urls_filled"] += 1

            # domains
            domains = rec.get("domains")
            if _is_nonempty_list(domains):
                stats[src]["domains_filled"] += 1

            # target_service
            if _is_nonempty_str(rec.get("target_service")):
                stats[src]["target_service_filled"] += 1

            # threat_claim
            if _is_nonempty_str(rec.get("threat_claim")):
                stats[src]["threat_claim_filled"] += 1

            # posted_at
            # (date 객체가 JSON에선 보통 "YYYY-MM-DD" 문자열로 들어가므로 문자열도 OK)
            posted_at = rec.get("posted_at")
            if posted_at is not None and str(posted_at).strip() != "":
                stats[src]["posted_at_filled"] += 1

        else:
            # CSV는 칼럼명이 프로젝트마다 달라질 수 있어, 최대한 관대하게 처리
            # source
            # urls: osint_seeds.urls / urls / url 같은 컬럼이 있을 수 있음
            urls = (rec.get("urls") or rec.get("osint_seeds.urls") or rec.get("url") or "").strip()
            if urls != "":
                stats[src]["urls_filled"] += 1

            domains = (rec.get("domains") or "").strip()
            if domains != "":
                stats[src]["domains_filled"] += 1

            target = (rec.get("target_service") or rec.get("target") or "").strip()
            if target != "":
                stats[src]["target_service_filled"] += 1

            actor = (rec.get("threat_claim") or rec.get("actor") or "").strip()
            if actor != "":
                stats[src]["threat_claim_filled"] += 1

            posted = (rec.get("posted_at") or "").strip()
            if posted != "":
                stats[src]["posted_at_filled"] += 1

    return stats


def print_report(stats: Dict[str, Dict[str, int]]) -> None:
    # 출력 정렬: total 내림차순
    rows: List[Tuple[str, Dict[str, int]]] = sorted(
        stats.items(), key=lambda kv: kv[1].get("total", 0), reverse=True
    )

    def fmt(n: int, total: int) -> str:
        return f"{n}/{total}"

    header = [
        "source",
        "total",
        "urls_filled",
        "domains_filled",
        "target_service_filled",
        "threat_claim_filled",
        "posted_at_filled",
    ]
    print("\t".join(header))

    for src, s in rows:
        total = s.get("total", 0)
        line = [
            src,
            str(total),
            fmt(s.get("urls_filled", 0), total),
            fmt(s.get("domains_filled", 0), total),
            fmt(s.get("target_service_filled", 0), total),
            fmt(s.get("threat_claim_filled", 0), total),
            fmt(s.get("posted_at_filled", 0), total),
        ]
        print("\t".join(line))


def main() -> int:
    # 우선 JSON 사용
    json_path = DEFAULT_JSON
    csv_path = DEFAULT_CSV

    if len(sys.argv) >= 2:
        json_path = Path(sys.argv[1])

    if json_path.exists():
        records = load_records_from_json(json_path)
        stats = compute_coverage(records, mode="json")
        print_report(stats)
        return 0

    # JSON이 없으면 CSV 시도
    if csv_path.exists():
        records = load_records_from_csv(csv_path)
        stats = compute_coverage(records, mode="csv")
        print_report(stats)
        return 0

    print("ERROR: data/leak_summary.json (or data/leak_summary.csv) not found.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

import json
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import date
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from .models import LeakRecord


# =====================================================
# MITRE 데이터 다운로드 & 로드
# =====================================================
MITRE_ENTERPRISE_URL = (
    "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"
)
LOCAL_MITRE_FILE = "enterprise-attack.json"


def ensure_mitre_file():
    """MITRE STIX JSON을 로컬에 유지"""
    if os.path.exists(LOCAL_MITRE_FILE):
        return True

    print("📥 MITRE 데이터 다운로드 중...")

    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1,
                    status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))

    try:
        response = session.get(MITRE_ENTERPRISE_URL, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ MITRE 데이터 다운로드 실패: {e}")
        return False

    with open(LOCAL_MITRE_FILE, "w", encoding="utf-8") as f:
        f.write(response.text)

    print("✅ MITRE 데이터 로컬 저장 완료")
    return True


def load_mitre_objects():
    if not ensure_mitre_file():
        return []

    with open(LOCAL_MITRE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    objects = data.get("objects", [])

    # intrusion-set 이름 lower-case로 저장
    for obj in objects:
        if obj.get("type") == "intrusion-set" and "name" in obj:
            obj["name_lower"] = obj["name"].lower()

    return objects


# =====================================================
# MITRE 검색 로직
# =====================================================
def search_intrusion_set(objects, group_name: str):
    """대소문자 무시 공격자 그룹 검색"""
    query = group_name.lower()
    return [
        obj for obj in objects
        if obj.get("type") == "intrusion-set"
        and query in obj.get("name_lower", "")
    ]


def get_relationships(objects, source_id):
    """intrusion-set → attack-pattern 관계"""
    return [
        obj for obj in objects
        if obj.get("type") == "relationship"
        and obj.get("source_ref") == source_id
        and "attack-pattern" in obj.get("target_ref", "")
    ]


def get_techniques(objects, technique_ids):
    """⭐ TTP 이름만 반환"""
    return [
        obj.get("name")
        for obj in objects
        if obj.get("type") == "attack-pattern" and obj.get("id") in technique_ids
    ]


# =====================================================
# OSINT Enrichment 함수
# =====================================================
def enrich_leakrecord_osint(record: LeakRecord) -> LeakRecord:
    """LeakRecord를 입력으로 받아 OSINT 기반 자동 보강"""

    objects = load_mitre_objects()
    if not objects:
        return record

    if record.osint_seeds is None:
        record.osint_seeds = {}

    # 1) MITRE 기반 Threat Claim 처리
    if record.threat_claim:
        groups = search_intrusion_set(objects, record.threat_claim)
        if groups:
            group = groups[0]

            # attack-pattern 관계 찾기
            rels = get_relationships(objects, group.get("id"))
            technique_ids = [r.get("target_ref") for r in rels]

            # ⭐ TTP 이름만 저장
            ttp_names = get_techniques(objects, technique_ids)
            record.osint_seeds["ttps"] = ttp_names

            # 기본 inference
            if not record.leak_types:
                record.leak_types = ["APT-attributed leak"]

            if record.country is None:
                record.country = "unknown"

            if record.target_service is None:
                record.target_service = "unknown service"

    # 2) 기타 기본 필드 보완
    record.author = record.author or "unknown"
    record.posted_at = record.posted_at or "unknown"
    record.estimated_volume = record.estimated_volume or "unknown"
    record.deal_terms = record.deal_terms or "unknown"

    record.file_formats = record.file_formats or []
    record.domains = record.domains or []
    record.screenshot_refs = record.screenshot_refs or []

    return record
# app/enrich_with_osint.py

from typing import Optional, List, Dict
import re

import requests
from bs4 import BeautifulSoup

from .models import LeakRecord
import os
import json


# ───────────────────────────────────────────────
# Malpedia 기능 (quicksearch + actor 페이지 파싱)
# ───────────────────────────────────────────────

BASE_URL = "https://malpedia.caad.fkie.fraunhofer.de"


def get_threat_claim(threat_claim: str) -> dict:
    """
    Malpedia quicksearch API 호출.
    threat_claim 문자열(예: 그룹명)을 needle 파라미터로 넘겨 검색 결과(JSON)를 반환.
    """
    url = f"{BASE_URL}/backend/quicksearch"
    params = {"needle": threat_claim}

    headers = {
        "Host": "malpedia.caad.fkie.fraunhofer.de",
        "Cookie": "csrftoken=KhRWGXtnaXiPR9m6dHxnGAeTXmzoorEb",
        "Sec-Ch-Ua-Platform": '"Linux"',
        "X-Requested-With": "XMLHttpRequest",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "*/*",
        "Sec-Ch-Ua": '"Chromium";v="139", "Not;A=Brand";v="99"',
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
        ),
        "Referer": "https://malpedia.caad.fkie.fraunhofer.de/",
    }

    response = requests.get(url, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()


def parse_actor_page(html: str) -> Dict[str, List[str]]:
    """
    Malpedia actor 페이지 HTML을 파싱해 description, references를 추출.
    """
    soup = BeautifulSoup(html, "html.parser")

    # <meta name="description" content="...">
    desc_tag = soup.find("meta", attrs={"name": "description"})
    description = desc_tag.get("content", "") if desc_tag else ""

    # 참고 링크들 (예: tr.clickable-row.clickable-row-newtab 의 data-href)
    reference_rows = soup.select("tr.clickable-row.clickable-row-newtab")
    references = [row.get("data-href") for row in reference_rows if row.get("data-href")]

    return {
        "description": description,
        "references": references,
    }


def fetch_first_item_details(quicksearch_response: dict) -> List[dict]:
    """
    quicksearch_response의 첫 번째 항목만 가져와서 HTML을 요청 후 파싱.
    Actor 여부와 상관없이 첫 번째 항목만 처리.
    """
    items = quicksearch_response.get("data", [])
    if not items:
        return []

    item = items[0]  # 첫 번째 항목만 사용
    relative_url = item.get("url")
    if not relative_url:
        return []

    full_url = BASE_URL + relative_url
    resp = requests.get(full_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    resp.raise_for_status()

    parsed = parse_actor_page(resp.text)

    return [
        {
            "name": item.get("name"),
            "url": full_url,
            "description": parsed["description"],
            "references": parsed["references"],
        }
    ]


def enrich_leakrecord_with_malpedia(leak: LeakRecord) -> LeakRecord:
    """
    LeakRecord.threat_claim을 기반으로 Malpedia 정보를 조회하고,
    actor 정보(description, references 등)를 leak.osint_seeds["malpedia"]에 원본으로 저장한 뒤
    description을 분석해 LeakRecord를 보강 후 반환.
    """

    if not leak.threat_claim:
        return leak

    try:
        # 1) Malpedia quicksearch
        quick_data = get_threat_claim(leak.threat_claim)
        first_item_details = fetch_first_item_details(quick_data)
    except Exception:
        # Malpedia 장애나 네트워크 오류 시 파이프라인이 깨지지 않도록 그대로 반환
        return leak

    if not first_item_details:
        return leak

    # 2) osint_seeds에 Malpedia 원본 정보 저장
    if leak.osint_seeds is None:
        leak.osint_seeds = {}

    leak.osint_seeds.setdefault("malpedia", {})
    leak.osint_seeds["malpedia"][leak.threat_claim] = {
        "original_data": first_item_details,  # Malpedia에서 가져온 원본 정보
    }

    # 3) description 기반 보강
    description = first_item_details[0].get("description", "")

    # -----------------------------
    # Country 추출 (예: "based in X", "in X")
    countries = re.findall(r"based in ([\w\s]+)|in ([\w\s]+)", description)
    countries = [c for tup in countries for c in tup if c]
    if countries and not leak.country:
        leak.country = countries[0].strip()

    # -----------------------------
    # Target service / 조직 (예: "targeting X")
    services = re.findall(
        r"targeting ([\w\s&]+?)(?:\.|,| and|$)",
        description,
        re.IGNORECASE,
    )
    if services and not leak.target_service:
        leak.target_service = services[0].strip()

    # -----------------------------
    # Domains (설명 안에 노출되는 도메인들)
    domains = re.findall(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b", description)
    if domains:
        if leak.domains:
            # 기존 도메인과 중복 제거 후 합치기
            merged = set(leak.domains)
            merged.update(domains)
            leak.domains = list(merged)
        else:
            leak.domains = list(set(domains))

    # -----------------------------
    # Leak types / 공격 수단 키워드
    leak_type_keywords = [
        "defacement attacks",
        "distributed denial-of-service attacks",
        "data leaks",
        "email",
        "password",
        "credential",
        "database",
    ]
    found_types = [
        kw for kw in leak_type_keywords if re.search(kw, description, re.IGNORECASE)
    ]
    if found_types:
        if leak.leak_types:
            merged_types = set(leak.leak_types)
            merged_types.update(found_types)
            leak.leak_types = list(merged_types)
        else:
            leak.leak_types = list(set(found_types))

    # -----------------------------
    # Confidence 추론
    desc_lower = description.lower()
    if any(word in desc_lower for word in ["observed", "demonstrated", "confirmed"]):
        leak.confidence = "high"
    elif "suspected" in desc_lower:
        leak.confidence = "medium"
    else:
        # Malpedia 설명이 애매하면 low로 default
        if not leak.confidence:
            leak.confidence = "low"

    # -----------------------------
    # Threat claim (비어 있으면 description에서 재추론)
    if not leak.threat_claim:
        match = re.search(
            r"\b([A-Z][a-zA-Z0-9]+(?:\s[A-Z][a-zA-Z0-9]+)*)\b",
            description,
        )
        if match:
            leak.threat_claim = match.group(1)

    return leak


# ───────────────────────────────────────────────
# 단순 heuristic OSINT용 상수들
# ───────────────────────────────────────────────

TLD_COUNTRY_MAP = {
    ".co.kr": "KR",
    ".go.kr": "KR",
    ".kr": "KR",
    ".jp": "JP",
    ".com": "Unknown",
    ".net": "Unknown",
    ".org": "Unknown",
}

SECTOR_KEYWORDS = {
    "university": "Education",
    "college": "Education",
    "school": "Education",
    "hospital": "Healthcare",
    "clinic": "Healthcare",
    "gov": "Government",
    "bank": "Finance",
}

GROUP_PROFILES: Dict[str, Dict] = {
    "sinobi": {
        "model": "double extortion",
        "typical_sectors": ["Manufacturing", "Services"],
        "ransom_style": "Data theft + encryption",
    },
    # 필요시 다른 그룹도 여기에 추가
    # "lockbit": {...},
}


def infer_country_from_domain(domains: List[str]) -> Optional[str]:
    """
    도메인 TLD를 기반으로 간단히 국가를 추론.
    """
    if not domains:
        return None

    for d in domains:
        d_lower = d.lower()
        for tld, country in TLD_COUNTRY_MAP.items():
            if d_lower.endswith(tld):
                return country
    return None


def infer_sector_from_victim_and_domain(
    victim: Optional[str],
    domains: List[str],
) -> Optional[str]:
    """
    피해자 이름/도메인 문자열에 포함된 키워드를 기반으로 섹터 추론.
    """
    text = " ".join([victim or "", *domains]).lower()
    for keyword, sector in SECTOR_KEYWORDS.items():
        if keyword in text:
            return sector
    return None


def enrich_leakrecord_with_heuristics(leak: LeakRecord) -> LeakRecord:
    """
    외부 API 없이, 우리가 가진 정보만으로 할 수 있는 OSINT 보강.

    - 도메인 TLD 기반 국가 추론
    - victim/domain 키워드 기반 섹터 추론
    - 사전 기반 group_profile 추가
    """
    seeds = dict(leak.osint_seeds) if leak.osint_seeds else {}

    # 1) country (이미 Malpedia가 채워줬으면 유지, 없으면 TLD 기반 추론)
    if not leak.country:
        inferred_country = infer_country_from_domain(leak.domains or [])
        if inferred_country:
            leak.country = inferred_country

    # 2) victim_profile (sector, country)
    victim_profile: Dict[str, str] = seeds.get("victim_profile", {})
    sector = infer_sector_from_victim_and_domain(
        leak.target_service,
        leak.domains or [],
    )
    if sector:
        victim_profile["sector"] = sector
    if leak.country:
        victim_profile["country"] = leak.country
    if victim_profile:
        seeds["victim_profile"] = victim_profile

    # 3) group_profile (단순 사전 기반 매핑)
    if leak.threat_claim:
        key = leak.threat_claim.lower()
        if key in GROUP_PROFILES:
            seeds["group_profile"] = GROUP_PROFILES[key]

    leak.osint_seeds = seeds
    return leak


# ───────────────────────────────────────────────
# MITRE ENTERPRISE ATT&CK (STIX 2.1)
# ───────────────────────────────────────────────
MITRE_JSON_URL = (
    "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"
)
MITRE_LOCAL_FILE = "enterprise-attack.json"


def ensure_mitre_file():
    if os.path.exists(MITRE_LOCAL_FILE):
        return True

    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))

    try:
        resp = session.get(MITRE_JSON_URL, timeout=20)
        resp.raise_for_status()
        with open(MITRE_LOCAL_FILE, "w", encoding="utf-8") as f:
            f.write(resp.text)
        return True
    except Exception:
        return False


def load_mitre_objects():
    if not ensure_mitre_file():
        return []

    with open(MITRE_LOCAL_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    objects = data.get("objects", [])
    for obj in objects:
        if obj.get("type") == "intrusion-set" and "name" in obj:
            obj["name_lower"] = obj["name"].lower()
    return objects


def mitre_search_intrusion_set(objects, group_name: str):
    q = group_name.lower()
    return [
        o for o in objects
        if o.get("type") == "intrusion-set"
        and q in o.get("name_lower", "")
    ]


def mitre_relationships(objects, source_id):
    return [
        o for o in objects
        if o.get("type") == "relationship"
        and o.get("source_ref") == source_id
        and "attack-pattern" in o.get("target_ref", "")
    ]


def mitre_attack_patterns(objects, technique_ids):
    return [
        o.get("name")
        for o in objects
        if o.get("type") == "attack-pattern"
        and o.get("id") in technique_ids
    ]


def enrich_with_mitre(leak: LeakRecord) -> LeakRecord:
    """MITRE 기반 보강"""
    objects = load_mitre_objects()
    if not objects:
        return leak

    if leak.threat_claim:
        groups = mitre_search_intrusion_set(objects, leak.threat_claim)
        if groups:
            group = groups[0]

            rels = mitre_relationships(objects, group.get("id"))
            technique_ids = [r.get("target_ref") for r in rels]
            ttp_names = mitre_attack_patterns(objects, technique_ids)

            leak.osint_seeds.setdefault("ttps", [])
            leak.osint_seeds["ttps"] = ttp_names

            leak.leak_types = leak.leak_types or ["APT-attributed leak"]
            leak.country = leak.country or "unknown"
            leak.target_service = leak.target_service or "unknown service"

    return leak


# ───────────────────────────────────────────────
# OSINT 통합 wrapper
# ───────────────────────────────────────────────

def enrich_leakrecord_with_osint(leak: LeakRecord) -> LeakRecord:
    """
    하나의 LeakRecord에 대해 수행할 모든 OSINT 보강을 한 곳에서 실행하는 wrapper.

    사용 예:
        from .enrich_with_osint import enrich_leakrecord_with_osint

        record = intermediate_to_leakrecord(...)
        record = enrich_leakrecord_with_osint(record)
    """

    # 1) Malpedia 기반 OSINT
    leak = enrich_leakrecord_with_malpedia(leak)

    # 2) 단순 heuristic 기반 OSINT
    leak = enrich_leakrecord_with_heuristics(leak)

    # 3)
    leak = enrich_with_mitre(leak)

    return leak


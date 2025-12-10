from dataclasses import dataclass, field
from datetime import date
from typing import Optional, List, Dict
import requests
from bs4 import BeautifulSoup
from .models import LeakRecord
import re


# ───────────────────────────────────────────────
# Malpedia 기능(quicksearch + actor 페이지 파싱)
# ───────────────────────────────────────────────
BASE_URL = "https://malpedia.caad.fkie.fraunhofer.de"


def get_threat_claim(threat_claim: str):
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

    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    return response.json()


def parse_actor_page(html: str):
    soup = BeautifulSoup(html, "html.parser")

    desc_tag = soup.find("meta", attrs={"name": "description"})
    description = desc_tag.get("content", "") if desc_tag else ""

    reference_rows = soup.select("tr.clickable-row.clickable-row-newtab")
    references = [row.get("data-href") for row in reference_rows if row.get("data-href")]

    return {
        "description": description,
        "references": references
    }


def fetch_first_item_details(quicksearch_response: dict):
    """
    quicksearch_response의 첫 번째 항목만 가져와서 HTML을 요청 후 파싱
    Actor 여부와 상관없이 첫 번째 항목 처리
    """
    items = quicksearch_response.get("data", [])
    if not items:
        return []

    item = items[0]  # 첫 번째 항목만
    relative_url = item.get("url")
    if not relative_url:
        return []

    full_url = BASE_URL + relative_url
    resp = requests.get(full_url, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()

    parsed = parse_actor_page(resp.text)

    return [{
        "name": item.get("name"),
        "url": full_url,
        "description": parsed["description"],
        "references": parsed["references"]
    }]



def enrich_leakrecord_with_malpedia(leak: LeakRecord) -> LeakRecord:
    """
    LeakRecord.threat_claim을 기반으로 Malpedia 정보를 조회하고,
    actor 정보(description, references 등)를 leak.osint_seeds["malpedia"]에 원본으로 저장한 뒤
    description을 분석해 LeakRecord를 보강 후 반환.
    """

    if not leak.threat_claim:
        return leak

    # 1) Malpedia quicksearch
    quick_data = get_threat_claim(leak.threat_claim)
    first_item_details = fetch_first_item_details(quick_data)

    if not first_item_details:
        return leak

    # 2) osint_seeds에 원본 저장
    leak.osint_seeds.setdefault("malpedia", {})
    leak.osint_seeds["malpedia"][leak.threat_claim] = {
        "original_data": first_item_details,  # 원본 Malpedia 정보
    }

    # 3) description 기반 보강
    description = first_item_details[0].get("description", "")

    # -----------------------------
    # Country
    countries = re.findall(r"based in ([\w\s]+)|in ([\w\s]+)", description)
    countries = [c for tup in countries for c in tup if c]
    if countries:
        leak.country = countries[0].strip()

    # -----------------------------
    # Target service / 조직
    services = re.findall(r"targeting ([\w\s&]+?)(?:\.|,| and|$)", description, re.IGNORECASE)
    if services:
        leak.target_service = services[0].strip()

    # -----------------------------
    # Domains
    domains = re.findall(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b", description)
    if domains:
        leak.domains = list(set(leak.domains + domains)) if leak.domains else domains

    # -----------------------------
    # Leak types / 공격 수단
    leak_type_keywords = ["defacement attacks", "distributed denial-of-service attacks", "data leaks", 
                          "email", "password", "credential", "database"]
    found_types = [kw for kw in leak_type_keywords if re.search(kw, description, re.IGNORECASE)]
    if found_types:
        leak.leak_types = list(set(leak.leak_types + found_types)) if leak.leak_types else found_types

    # -----------------------------
    # Confidence
    if any(word in description.lower() for word in ["observed", "demonstrated", "confirmed"]):
        leak.confidence = "high"
    elif "suspected" in description.lower():
        leak.confidence = "medium"
    else:
        leak.confidence = "low"

    # -----------------------------
    # Threat claim
    if not leak.threat_claim:
        match = re.search(r"\b([A-Z][a-zA-Z0-9]+(?:\s[A-Z][a-zA-Z0-9]+)*)\b", description)
        if match:
            leak.threat_claim = match.group(1)

    return leak

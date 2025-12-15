# app/notifier.py

from __future__ import annotations

import os
from typing import Optional, Any

import requests

from .models import LeakRecord


# =============================================================================
# Helpers
# =============================================================================
def _as_csv(value: Any) -> str:
    """
    list[str] | str | None 등 다양한 형태를 안전하게 "a, b, c" 문자열로 변환.
    - None/empty -> "N/A"
    - str -> 그대로
    - iterable -> join
    - 그 외 -> str(value)
    """
    if value is None:
        return "N/A"
    if isinstance(value, str):
        v = value.strip()
        return v if v else "N/A"
    try:
        # 리스트/튜플/세트 등일 때
        items = list(value)
        if not items:
            return "N/A"
        # 문자열이 아닌 값이 섞여도 안전하게 변환
        return ", ".join(str(x) for x in items)
    except TypeError:
        return str(value)


def _truncate(text: Optional[str], max_len: int = 140) -> str:
    if not text:
        return "N/A"
    t = text.strip()
    if not t:
        return "N/A"
    return t if len(t) <= max_len else t[: max_len - 3] + "..."


# =============================================================================
# 1) 콘솔 알림 (안정화/정리 버전)
# =============================================================================
def notify_new_leak(record: LeakRecord) -> None:
    """새 유출 정보가 추가될 때 콘솔에 알림을 출력. (필드 누락/타입 불일치 방어)"""

    def _val(name: str, default="N/A"):
        v = getattr(record, name, None)
        if v is None:
            return default
        if isinstance(v, str):
            v = v.strip()
            return v if v else default
        return v

    def _csv(name: str) -> str:
        v = getattr(record, name, None)
        if not v:
            return "N/A"
        if isinstance(v, str):
            return v.strip() or "N/A"
        try:
            return ", ".join(str(x) for x in list(v))
        except Exception:
            return str(v)

    title = _val("post_title")
    source = _val("source")
    target = _val("target_service")
    domains = _csv("domains")
    leak_types = _csv("leak_types")
    volume = _val("estimated_volume", default="Unknown")
    confidence = _val("confidence")
    collected_at = _val("collected_at")
    posted_at = _val("posted_at", default="")  # 없으면 안 찍어도 됨

    print("\n" + "=" * 72)
    print("🔔 [NEW LEAK DETECTED]")
    print(f"- Source        : {source}")
    print(f"- Collected At  : {collected_at}")
    if posted_at:
        print(f"- Posted At     : {posted_at}")
    print(f"- Title         : {title}")
    print(f"- Target Service: {target}")
    print(f"- Domains       : {domains}")
    print(f"- Leak Types    : {leak_types}")
    print(f"- Volume        : {volume}")
    print(f"- Confidence    : {confidence}")
    print("=" * 72 + "\n")


# =============================================================================
# 2) Slack 알림 (기존 유지)
# =============================================================================
def notify_slack(record: LeakRecord, webhook_url: Optional[str] = None) -> None:
    """
    Slack Incoming Webhook으로 알림 전송.
    - webhook_url 인자가 없으면 환경변수 SLACK_WEBHOOK_URL 사용
    """
    url = (webhook_url or os.getenv("SLACK_WEBHOOK_URL", "")).strip()

    if not url:
        print("[WARN] SLACK_WEBHOOK_URL is not set. Skip Slack notification.")
        return

    domains = _as_csv(getattr(record, "domains", None))
    leak_types = _as_csv(getattr(record, "leak_types", None))
    volume = getattr(record, "estimated_volume", None)
    volume = volume if volume is not None else "Unknown"

    text = (
        "*🚨 New Darkweb Leak Detected*\n"
        f"*Source:* {record.source}\n"
        f"*Title:* {getattr(record, 'post_title', '')}\n"
        f"*Target:* {getattr(record, 'target_service', None) or 'N/A'}\n"
        f"*Domains:* {domains}\n"
        f"*Leak Types:* {leak_types}\n"
        f"*Volume:* {volume}\n"
        f"*Confidence:* {getattr(record, 'confidence', None)}\n"
        f"*Collected At:* {getattr(record, 'collected_at', None)}\n"
    )

    try:
        resp = requests.post(url, json={"text": text}, timeout=10)
        if resp.status_code >= 400:
            print(f"[ERROR] Slack webhook failed: {resp.status_code} {resp.text}")
        else:
            print("[OK] Slack notification sent.")
    except Exception as e:
        print(f"[ERROR] Slack webhook request error: {e}")


# =============================================================================
# 3) 통합 알림 (main_demo_telegram.py가 기대하는 함수)
# =============================================================================
def notify_all(record: LeakRecord) -> None:
    """콘솔 + Slack 모두 알림."""
    notify_new_leak(record)
    notify_slack(record)

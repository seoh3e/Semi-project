
import re
from urllib.parse import urlparse
from datetime import date
from typing import Optional, List, Dict

from pyrogram import Client
from pyrogram.types import Message

from .models import LeakRecord
from .storage import add_leak_record
from .notifier import notify_new_leak


# ─────────────────────────────────────────
# 1) 텔레그램 클라이언트 설정
# ─────────────────────────────────────────
API_ID = 34221825          # <- 본인 api_id 
API_HASH = "44a948711e6034324886bebc6abb0a5d"  # <- 본인 api_hash 
CHANNEL = "@ctifeeds"    # Cyber Threat Intelligence Feeds


app = Client("ctifeeds_session", api_id=API_ID, api_hash=API_HASH)


# ─────────────────────────────────────────
# 2) 유틸 함수들
# ─────────────────────────────────────────

def extract_first_url(text: str) -> Optional[str]:
    """문장 안에서 최초의 http/https URL 하나 추출."""
    m = re.search(r"(https?://\S+)", text)
    if not m:
        return None
    # 뒤에 붙은 괄호/마침표 같은 건 대충 제거
    return m.group(1).rstrip(").,")


def domain_from_url(url: str) -> Optional[str]:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return None


def extract_attacker_aliases(text: str) -> List[str]:
    """
    예:
      - 'Recent defacement reported by H4x0r: https://...'
      - 'Hacked BY XYZEAZ'
    이런 패턴에서 공격자/그룹 닉네임 뽑기.
    """
    aliases: List[str] = []

    m = re.search(r"reported by\s+([^:]+):", text, re.IGNORECASE)
    if m:
        aliases.append(m.group(1).strip())

    m = re.search(r"Hacked BY\s+([^\s]+)", text, re.IGNORECASE)
    if m:
        aliases.append(m.group(1).strip())

    # 중복 제거
    return list(dict.fromkeys(aliases))


# ─────────────────────────────────────────
# 3) ctifeeds 한 메시지 → LeakRecord 변환
# ─────────────────────────────────────────

def parse_ctifeeds_message(message: Message) -> Optional[LeakRecord]:
    """
    Cyber Threat Intelligence Feeds(@ctifeeds)의 메시지 1건을
    LeakRecord로 변환. defacement 관련이 아닌 건 None 리턴.
    """
    text = (message.text or message.caption or "").strip()
    if not text:
        return None

    lower = text.lower()

    # defacement / breach / leak 키워드가 없는 글은 스킵
    keywords = ["defacement", "data breach", "breach", "leak"]
    if not any(k in lower for k in keywords):
        return None

    url = extract_first_url(text)
    domain = domain_from_url(url) if url else None
    attacker_aliases = extract_attacker_aliases(text)

    # 제목은 전체 문장을 그대로 사용 (필요하면 잘라 써도 됨)
    post_title_val = text

    # 게시 시각
    posted_at_val = message.date.date() if message.date else None

    # 작성자(채널 메시지는 보통 없음)
    author_val = message.from_user.username if message.from_user else None

    # leak_types 대충 분류 (데이터 유출 vs 웹디페이스)
    leak_types: List[str] = []
    if "defacement" in lower:
        leak_types.append("web_defacement")
    if "data breach" in lower or "breach" in lower or "leak" in lower:
        leak_types.append("data_breach")

    # confidence: 뉴스/피드 기반이라 일단 medium 정도
    confidence_val = "medium"

    # OSINT용 seed 정보
    osint_seeds: Dict = {
        "domains": [domain] if domain else [],
        "urls": [url] if url else [],
        "attacker_aliases": attacker_aliases,
        "raw_text": text,
    }

    record = LeakRecord(
        collected_at=date.today(),
        source="Telegram:Cyber Threat Intelligence Feeds",
        post_title=post_title_val,
        post_id=str(message.id),
        author=author_val,
        posted_at=posted_at_val,

        leak_types=leak_types,
        estimated_volume=None,
        file_formats=[],

        target_service=domain,      # 일단 도메인 기준으로 서비스 이름 대체
        domains=[domain] if domain else [],
        country=None,               # 필요하면 나중에 따로 추출

        threat_claim=text,
        deal_terms=None,
        confidence=confidence_val,

        screenshot_refs=[],
        osint_seeds=osint_seeds,
    )

    return record


# ─────────────────────────────────────────
# 4) 최근 메시지 여러 개 불러와서 저장 + 알림
# ─────────────────────────────────────────

def fetch_ctifeeds_defacements(limit: int = 50) -> None:
    """
    @ctifeeds 채널 history 중 최근 limit개 메시지를 가져와서
    defacement/유출 관련 글만 LeakRecord로 저장하고 알림 출력.
    """
    parsed_count = 0

    with app:
        for message in app.get_chat_history(CHANNEL, limit=limit):
            record = parse_ctifeeds_message(message)
            if record is None:
                continue

            parsed_count += 1
            add_leak_record(record)
            notify_new_leak(record)

    print(f"[INFO] ctifeeds에서 {parsed_count}건의 유출/defacement 이벤트를 파싱했습니다.")


if __name__ == "__main__":
    fetch_ctifeeds_defacements(limit=30)

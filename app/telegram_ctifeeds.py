# app/telegram_ctifeeds.py

import re
from datetime import date
from typing import Optional, List
from .models import IntermediateEvent, LeakRecord
from telethon.tl.types import MessageMediaWebPage,WebPage


# ─────────────────────────────────────────────
# 1) raw_text → IntermediateEvent
# ─────────────────────────────────────────────


def parse_ctifeeds(
    raw_text: str, message_id=None, message_url=None,message_media=None
) -> IntermediateEvent:
    """
    ctifeeds 채널 메시지 파서.
    """

    urls: List[str] = []
    victim = None
    group = None
    published_date_text = None

    # 기본 포맷:
    # Recent defacement reported by Hax.or: http://psb.mikenongomulyo.sch.id http://psb.mikenongomulyo.sch.id

    # MessageMediaWebPage(webpage=WebPage(id=8771885212922184846, url='https://psb.mikenongomulyo.sch.id/', display_url='psb.mikenongomulyo.sch.id', hash=0, has_large_media=False, video_cover_photo=False, type='article', site_name='psb.mikenongomulyo.sch.id', title='PPDB ONLINE | HACKED BY MIKU', description='Mari bergabung Bersama Kami di HACKED BY MIKU, Pendaftaran Peserta didik Baru Tahun 2026/2027 Kembali dibuka', photo=None, embed_url=None, embed_type=None, embed_width=None, embed_height=None, duration=None, author=None, document=None, cached_page=None, attributes=[]))

    if message_media:
        urls.append(message_media.webpage.display_url)

        victim=message_media.webpage.site_name

        group=message_media.webpage.title[message_media.webpage.title.lower().find("hacked by")+10:]

    return IntermediateEvent(
        source_channel="@ctifeeds",
        raw_text=raw_text,
        message_id=message_id,
        message_url=message_url,
        group_name=group,
        victim_name=victim,
        published_at_text=published_date_text,
        urls=urls,
        tags=[],
    )


# ─────────────────────────────────────────────
# 2) IntermediateEvent → LeakRecord 변환기
# ─────────────────────────────────────────────


def intermediate_to_ctifeeds_leakrecord(event: IntermediateEvent) -> LeakRecord:
    """
    파싱된 IntermediateEvent → LeakRecord 표준 구조 변환
    """

    return LeakRecord(
        collected_at=date.today(),
        source=event.source_channel,
        post_title=f"{event.group_name or ''} → {event.victim_name or ''}",
        post_id=str(event.message_id) if event.message_id else '',
        author=None,
        posted_at=None,
        leak_types=[],
        estimated_volume=None,
        file_formats=[],
        target_service=event.victim_name,
        domains=event.urls,
        country=None,
        threat_claim=event.group_name,
        deal_terms=None,
        confidence="medium",
        screenshot_refs=[],
        osint_seeds={"urls": event.urls},
    )

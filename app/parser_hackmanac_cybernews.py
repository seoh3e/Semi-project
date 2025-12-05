# app/parser_hackmanac_cybernews.py
from datetime import date, datetime
from typing import List, Optional, Any
import re
import dns.resolver

from .models import LeakRecord

# ------------------------------------------------------------
# Helper regexes & patterns
# ------------------------------------------------------------
FLAG_RE = re.compile(r"([\U0001F1E6-\U0001F1FF]{2})")
SOURCE_URL_RE = re.compile(r"^source\s*[:\-]?\s*(?P<url>https?://\S+)", re.IGNORECASE)
OBSERVED_RE = re.compile(r"^observed\s*[:\-]\s*(?P<obs>.+)$", re.IGNORECASE)
CLAIM_RE = re.compile(r"\bclaims?\b", re.IGNORECASE)
ESTIMATED_VOLUME_RE = re.compile(
    r"(?P<num>[\d,\.]+)\s*(?P<unit>(?:kb|mb|gb|tb|pb|k|m|b|records|files|entries))\b",
    re.IGNORECASE,
)
FILE_FORMAT_RE = re.compile(r"\b(pdf|csv|xls|xlsx|txt|json|sql|zip|rar|7z)\b", re.IGNORECASE)

# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------
def parse_observed_date(raw: str) -> Optional[date]:
    if not raw:
        return None
    raw = raw.strip()
    fmts = ["%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"]
    for fmt in fmts:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def normalize_estimated_volume(match_obj: re.Match) -> Optional[str]:
    if not match_obj:
        return None
    num = match_obj.group("num")
    unit = match_obj.group("unit").upper()
    return f"{num} {unit}"


def extract_first_flag(text: str) -> Optional[str]:
    m = FLAG_RE.search(text or "")
    return m.group(1) if m else None


def sentences(text: str) -> List[str]:
    parts = re.split(r"[\.!?\n]", text)
    return [p.strip() for p in parts if p.strip()]

# ------------------------------------------------------------
# Screenshot extraction from Telethon Message object
# ------------------------------------------------------------
def extract_screenshot_refs_from_msg(msg: Any) -> List[str]:
    refs: List[str] = []
    try:
        if getattr(msg, "photo", None):
            pid = getattr(msg.photo, "id", None) or getattr(msg.photo, "access_hash", None)
            refs.append(f"photo_{pid}.jpg" if pid else "photo")
    except Exception:
        pass

    try:
        doc = getattr(msg, "document", None)
        if doc:
            filename = None
            attrs = getattr(doc, "attributes", []) or []
            for a in attrs:
                if hasattr(a, "file_name") and a.file_name:
                    filename = a.file_name
                    break
            if not filename:
                did = getattr(doc, "id", None) or getattr(doc, "access_hash", None)
                filename = f"document_{did}" if did else "document"
            refs.append(filename)
    except Exception:
        pass

    try:
        media = getattr(msg, "media", None)
        if media and hasattr(media, "webpage") and getattr(media.webpage, "photo", None):
            wp_photo = media.webpage.photo
            pid = getattr(wp_photo, "id", None) or getattr(wp_photo, "access_hash", None)
            refs.append(f"webpage_photo_{pid}.jpg" if pid else "webpage_photo")
    except Exception:
        pass

    try:
        text = msg.message or ""
        for m in re.findall(r"\b([\w\-\./]+\.(?:png|jpg|jpeg|webp))\b", text, re.IGNORECASE):
            refs.append(m)
    except Exception:
        pass

    seen = set()
    out: List[str] = []
    for r in refs:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out

# ------------------------------------------------------------
# Extract mid-section fields
# ------------------------------------------------------------
def extract_mid_section_fields(raw: str, title_line: str):
    lines = raw.splitlines()
    try:
        start_idx = next(i for i, ln in enumerate(lines) if title_line and title_line in ln)
    except StopIteration:
        try:
            start_idx = next(i for i, ln in enumerate(lines) if FLAG_RE.search(ln))
        except StopIteration:
            start_idx = 0
    try:
        end_idx = next(i for i, ln in enumerate(lines[start_idx + 1:], start=start_idx + 1) if ln.strip().lower().startswith("sector:"))
    except StopIteration:
        end_idx = len(lines)

    section_lines = [ln.strip() for ln in lines[start_idx + 1:end_idx] if ln.strip()]
    section_text = " ".join(section_lines)

    leak_types: List[str] = []
    estimated_volume: Optional[str] = None
    file_formats: List[str] = []
    deal_terms: Optional[str] = None

    if not section_text:
        return leak_types, estimated_volume, file_formats, deal_terms

    lower = section_text.lower()
    keywords = [
        ("patients", "Patients"), ("patient", "Patients"), ("data", "Data"), ("database", "Database"),
        ("records", "Records"), ("files", "Files"), ("documents", "Documents"), ("emails", "Emails"),
        ("medical", "Medical"), ("internal", "Internal")
    ]
    for kw, label in keywords:
        if kw in lower and label not in leak_types:
            leak_types.append(label)

    m_vol = ESTIMATED_VOLUME_RE.search(section_text)
    if m_vol:
        estimated_volume = normalize_estimated_volume(m_vol)

    for fm in FILE_FORMAT_RE.findall(section_text):
        up = fm.upper()
        if up not in file_formats:
            file_formats.append(up)

    m_price = re.search(r"(for\s+\$\s*[\d,\.]+|\$\s*[\d,\.]+|\d+\s*btc)", section_text, re.IGNORECASE)
    if m_price:
        deal_terms = m_price.group(0).strip()
    else:
        if re.search(r"\bfor sale\b", lower) or re.search(r"\bsell(?:ing|s)?\b", lower):
            deal_terms = "for sale"

    return leak_types, estimated_volume, file_formats, deal_terms

# ------------------------------------------------------------
# Domain lookup using DNS
# ------------------------------------------------------------
def lookup_domain_dns(service_name: str) -> list[str]:
    if not service_name:
        return []
    candidates = [
        f"{service_name.replace(' ', '').lower()}.com",
        f"{service_name.replace(' ', '').lower()}.net",
        f"{service_name.replace(' ', '').lower()}.org",
    ]
    valid = []
    for dom in candidates:
        try:
            answers = dns.resolver.resolve(dom, 'A')
            if answers:
                valid.append(dom)
        except Exception:
            continue
    return valid

# ------------------------------------------------------------
# Main parser
# ------------------------------------------------------------
def parse_telegram_message(msg: Any) -> LeakRecord:
    raw_text = getattr(msg, "raw_text", None) or getattr(msg, "message", "") or ""

    source: Optional[str] = None
    post_title: str = ""
    post_id: Optional[str] = str(getattr(msg, "id", None)) if getattr(msg, "id", None) else None
    author: Optional[str] = None
    posted_at: Optional[date] = None
    leak_types: List[str] = []
    estimated_volume: Optional[str] = None
    file_formats: List[str] = []
    target_service: str = ""
    domains: List[str] = []
    country: Optional[str] = None
    threat_claim: Optional[str] = None
    deal_terms: Optional[str] = None
    confidence: str = "unknown"
    screenshot_refs: List[str] = []

    try:
        if getattr(msg, "chat", None) and getattr(msg.chat, "title", None):
            author = msg.chat.title
        else:
            sender = getattr(msg, "sender", None)
            if sender:
                username = getattr(sender, "username", None)
                if username:
                    author = username
                else:
                    fn = getattr(sender, "first_name", "") or ""
                    ln = getattr(sender, "last_name", "") or ""
                    author = (fn + " " + ln).strip() or None
    except Exception:
        author = None

    lines = [ln for ln in (raw_text or "").splitlines()]
    cleaned = [ln.strip() for ln in lines if ln and ln.strip() and ln.strip() != "—"]

    first_flag_line = None
    for ln in cleaned:
        if FLAG_RE.search(ln):
            first_flag_line = ln
            break
    if not first_flag_line:
        first_flag_line = cleaned[0] if cleaned else ""

    post_title = first_flag_line or ""
    flag = extract_first_flag(raw_text)
    if flag:
        cp = [ord(ch) - 0x1F1E6 for ch in flag]
        country = "".join(chr(c + ord("A")) for c in cp)

    if post_title and " - " in post_title:
        parts = post_title.split(" - ", 1)
        target_service = parts[1].strip()

    try:
        start_index = lines.index(first_flag_line)
    except ValueError:
        start_index = 0
    rest_lines = lines[start_index + 1 :] if start_index is not None else lines

    for ln in rest_lines:
        if not ln or not ln.strip():
            continue
        s = ln.strip()
        m_src = SOURCE_URL_RE.match(s)
        if m_src and not source:
            source = m_src.group("url").strip()
            continue
        m_obs = OBSERVED_RE.match(s)
        if m_obs and not posted_at:
            dt = parse_observed_date(m_obs.group("obs"))
            if dt:
                posted_at = dt
            continue
        if not threat_claim and CLAIM_RE.search(s):
            for sent in sentences(s):
                if CLAIM_RE.search(sent):
                    threat_claim = sent
                    break
            if not threat_claim:
                threat_claim = s

    lt, vol, fmts, deal = extract_mid_section_fields(raw_text, first_flag_line)
    if lt:
        leak_types = lt
    if vol:
        estimated_volume = vol
    if fmts:
        file_formats = fmts
    if deal:
        deal_terms = deal

    screenshot_refs = extract_screenshot_refs_from_msg(msg)

    if target_service:
        domains = lookup_domain_dns(target_service)

    record = LeakRecord(
        collected_at=date.today(),
        source=source or "Telegram Feed",
        post_title=post_title,
        post_id=post_id,
        author=author,
        posted_at=posted_at,
        leak_types=leak_types,
        estimated_volume=estimated_volume,
        file_formats=file_formats,
        target_service=target_service,
        domains=domains,
        country=country,
        threat_claim=threat_claim,
        deal_terms=deal_terms,
        confidence=confidence,
        screenshot_refs=screenshot_refs,
        osint_seeds={"raw_message": raw_text},
    )

    return record


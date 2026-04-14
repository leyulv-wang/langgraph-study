from __future__ import annotations

import datetime as dt
import hashlib
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from agent.utils.http_client import request
from agent.utils.rate_limit import RateLimiter
from agent.utils.text import extract_keywords, normalize_whitespace, simple_summary


def _hash(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8", errors="ignore")).hexdigest()[:16]


def _parse_rfc2822(s: str) -> Optional[dt.datetime]:
    try:
        from email.utils import parsedate_to_datetime

        return parsedate_to_datetime(s)
    except Exception:
        return None


def _parse_atom_time(s: str) -> Optional[dt.datetime]:
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _strip_html(html: str) -> str:
    t = re.sub(r"<[^>]+>", " ", html or "")
    return normalize_whitespace(t)


def _safe_text(el: Optional[ET.Element]) -> str:
    return (el.text or "").strip() if el is not None else ""


def fetch_feed(
    url: str,
    *,
    timeout_sec: int = 20,
    limiter: Optional[RateLimiter] = None,
    max_requests_per_minute: int = 30,
) -> str:
    if limiter is None:
        limiter = RateLimiter(max_requests_per_minute)
    limiter.acquire()
    resp = request("GET", url, headers={"User-Agent": "langgraph-demo"}, timeout_sec=timeout_sec, retries=3)
    return resp.text()


def parse_rss(xml_text: str, source: str) -> List[Dict[str, Any]]:
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        return []
    items: List[Dict[str, Any]] = []
    for it in channel.findall("item"):
        title = _safe_text(it.find("title"))
        link = _safe_text(it.find("link"))
        guid = _safe_text(it.find("guid")) or link or title
        pub_date = _safe_text(it.find("pubDate"))
        published = _parse_rfc2822(pub_date)
        desc = _safe_text(it.find("description"))
        text = _strip_html(desc)
        items.append(
            {
                "id": _hash(guid),
                "source": source,
                "title": title,
                "url": link,
                "published_at": published.isoformat() if published else "",
                "content": text,
            }
        )
    return items


def parse_atom(xml_text: str, source: str) -> List[Dict[str, Any]]:
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_text)
    entries = root.findall("a:entry", ns)
    items: List[Dict[str, Any]] = []
    for e in entries:
        title = _safe_text(e.find("a:title", ns))
        updated = _safe_text(e.find("a:updated", ns))
        published = _safe_text(e.find("a:published", ns)) or updated
        t = _parse_atom_time(published)
        url = ""
        for link in e.findall("a:link", ns):
            if link.get("rel") in (None, "", "alternate"):
                url = link.get("href") or url
        summary = _safe_text(e.find("a:summary", ns))
        content = _strip_html(summary)
        guid = _safe_text(e.find("a:id", ns)) or url or title
        items.append(
            {
                "id": _hash(guid),
                "source": source,
                "title": title,
                "url": url,
                "published_at": t.isoformat() if t else "",
                "content": content,
            }
        )
    return items


def dedupe_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for it in items:
        k = (it.get("url") or it.get("title") or "")[:512].strip()
        if not k:
            continue
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


def enrich_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for it in items:
        text = f"{it.get('title','')} {it.get('content','')}"
        out.append(
            {
                **it,
                "keywords": extract_keywords(text),
                "summary": simple_summary(it.get("content", "")),
            }
        )
    return out


def fetch_ai_news(
    *,
    sources: List[Dict[str, str]],
    days: int = 14,
    timeout_sec: int = 20,
    max_requests_per_minute: int = 30,
) -> List[Dict[str, Any]]:
    limiter = RateLimiter(max_requests_per_minute)
    all_items: List[Dict[str, Any]] = []
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=max(1, int(days)))

    for src in sources:
        name = src.get("name") or "unknown"
        url = src.get("url") or ""
        if not url:
            continue
        typ = (src.get("type") or "rss").lower()
        xml_text = fetch_feed(url, timeout_sec=timeout_sec, limiter=limiter, max_requests_per_minute=max_requests_per_minute)
        try:
            parsed = parse_atom(xml_text, name) if typ == "atom" else parse_rss(xml_text, name)
        except Exception:
            continue
        for it in parsed:
            ts = it.get("published_at") or ""
            try:
                t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None
            except Exception:
                t = None
            if t and t.tzinfo is None:
                t = t.replace(tzinfo=dt.timezone.utc)
            if t and t < since:
                continue
            all_items.append(it)

    all_items = dedupe_items(all_items)
    all_items = enrich_items(all_items)
    all_items.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    return all_items


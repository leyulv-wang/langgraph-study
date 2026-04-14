from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, List


_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
    "you",
    "your",
    "我",
    "你",
    "他",
    "她",
    "它",
    "我们",
    "你们",
    "他们",
    "的",
    "了",
    "和",
    "与",
    "及",
    "在",
    "是",
    "为",
    "对",
    "把",
    "将",
    "一个",
    "一种",
    "可以",
    "我们",
    "他们",
}


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def simple_summary(text: str, max_sentences: int = 2, max_chars: int = 280) -> str:
    t = normalize_whitespace(text)
    if not t:
        return ""
    parts = re.findall(r"[^。！？.!?]+[。！？.!?]?", t)
    parts = [p.strip() for p in parts if p and p.strip()]
    summary = "".join(parts[:max_sentences]).strip()
    if len(summary) > max_chars:
        summary = summary[: max_chars - 1].rstrip() + "…"
    return summary


def extract_keywords(text: str, top_k: int = 8) -> List[str]:
    t = normalize_whitespace(text).lower()
    tokens = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", t)
    tokens = [tok for tok in tokens if tok not in _STOPWORDS and len(tok) >= 2]
    if not tokens:
        return []
    counts = Counter(tokens)
    return [w for w, _ in counts.most_common(top_k)]


def stable_dedupe(items: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for it in items:
        k = (it or "").strip()
        if not k:
            continue
        if k in seen:
            continue
        seen.add(k)
        out.append(k)
    return out

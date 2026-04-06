from __future__ import annotations

from typing import Any, Dict, List

from agent.config import load_config
from agent.state import AppState
from agent.tools.news_tools import fetch_ai_news


def news_fetch(state: AppState) -> Dict[str, Any]:
    cfg = load_config()
    params = state.get("params", {})
    days = int(params.get("news_days", params.get("days", 14)))
    sources = list(cfg.news.get("sources") or [])

    items: List[Dict[str, Any]] = fetch_ai_news(
        sources=sources,
        days=days,
        timeout_sec=int(cfg.news.get("request_timeout_sec", 20)),
        max_requests_per_minute=int(cfg.limits.get("news_requests_per_minute", 30)),
    )
    return {"news_items": items}


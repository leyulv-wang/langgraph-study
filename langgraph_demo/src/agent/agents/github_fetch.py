from __future__ import annotations

from typing import Any, Dict, List

from agent.config import load_config
from agent.state import AppState
from agent.tools.github_tools import get_hot_ai_repos


def github_fetch(state: AppState) -> Dict[str, Any]:
    cfg = load_config()
    params = state.get("params", {})
    days = int(params.get("days", 14))
    topics = list(params.get("github_topics") or cfg.github.get("default_topics") or [])
    languages = list(params.get("github_languages") or cfg.github.get("default_languages") or [])
    limit = int(params.get("github_limit", cfg.github.get("default_limit", 20)))

    repos: List[Dict[str, Any]] = get_hot_ai_repos(
        days=days,
        topics=topics,
        languages=languages,
        limit=limit,
        base_url=str(cfg.github.get("base_url", "https://api.github.com")),
        max_requests_per_minute=int(cfg.limits.get("github_requests_per_minute", 30)),
        timeout_sec=int(cfg.github.get("request_timeout_sec", 20)),
    )
    return {"github_projects": repos}


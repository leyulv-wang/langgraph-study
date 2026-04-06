from __future__ import annotations

import datetime as dt
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from agent.utils.http_client import request
from agent.utils.rate_limit import RateLimiter


_GITHUB_GRAPHQL = "https://api.github.com/graphql"


def _iso_date(d: dt.datetime) -> str:
    return d.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def _get_token() -> str:
    return os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or ""


def _headers(token: str) -> Dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "langgraph-demo",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _graphql_headers(token: str) -> Dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "langgraph-demo",
        "Content-Type": "application/json",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _repo_to_item(repo: Dict[str, Any], star_growth: Optional[int] = None) -> Dict[str, Any]:
    return {
        "full_name": repo.get("full_name") or repo.get("fullName"),
        "html_url": repo.get("html_url") or repo.get("url"),
        "description": repo.get("description") or "",
        "language": repo.get("language") or repo.get("primaryLanguage", {}).get("name"),
        "topics": repo.get("topics") or repo.get("repositoryTopics"),
        "stars": repo.get("stargazers_count") or repo.get("stargazerCount") or 0,
        "forks": repo.get("forks_count") or repo.get("forkCount") or 0,
        "open_issues": repo.get("open_issues_count") or repo.get("openIssues", {}).get("totalCount") or 0,
        "archived": bool(repo.get("archived") or False),
        "license": (repo.get("license") or {}).get("spdx_id") if isinstance(repo.get("license"), dict) else repo.get("license"),
        "updated_at": repo.get("pushed_at") or repo.get("updatedAt"),
        "star_growth": star_growth,
    }


def search_candidate_repos(
    *,
    topics: List[str],
    languages: List[str],
    since: dt.datetime,
    limit: int,
    base_url: str = "https://api.github.com",
    limiter: Optional[RateLimiter] = None,
    timeout_sec: int = 20,
) -> List[Dict[str, Any]]:
    token = _get_token()
    headers = _headers(token)
    base = base_url.rstrip("/")
    items: List[Dict[str, Any]] = []

    query_parts = [f"pushed:>={since.date().isoformat()}"]
    if topics:
        topic_q = " ".join([f"topic:{t}" for t in topics])
        query_parts.append(f"({topic_q})")
    if languages:
        lang_q = " ".join([f"language:{l}" for l in languages])
        query_parts.append(f"({lang_q})")

    q = " ".join(query_parts)
    url = f"{base}/search/repositories?q={_url_encode(q)}&sort=stars&order=desc&per_page={min(100, max(1, limit))}"
    if limiter:
        limiter.acquire()
    resp = request("GET", url, headers=headers, timeout_sec=timeout_sec, retries=3)
    if resp.status != 200:
        return []
    data = resp.json()
    for it in data.get("items", [])[:limit]:
        items.append(it)
    return items


def _url_encode(s: str) -> str:
    from urllib.parse import quote

    return quote(s, safe="")


def _graphql_star_growth(
    *,
    full_name: str,
    since: dt.datetime,
    token: str,
    limiter: Optional[RateLimiter],
    timeout_sec: int,
) -> Optional[int]:
    if not token:
        return None

    owner, repo = full_name.split("/", 1)
    after: Optional[str] = None
    count = 0
    since_iso = _iso_date(since.astimezone(dt.timezone.utc))

    while True:
        query = """
query($owner:String!, $name:String!, $after:String) {
  repository(owner:$owner, name:$name) {
    stargazers(first:100, after:$after, orderBy:{field:STARRED_AT, direction:DESC}) {
      edges { starredAt }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""
        variables = {"owner": owner, "name": repo, "after": after}
        payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        if limiter:
            limiter.acquire()
        resp = request(
            "POST",
            _GITHUB_GRAPHQL,
            headers=_graphql_headers(token),
            data=payload,
            timeout_sec=timeout_sec,
            retries=3,
        )
        if resp.status != 200:
            return None
        body = resp.json()
        edges = (
            (((body.get("data") or {}).get("repository") or {}).get("stargazers") or {}).get("edges")
            or []
        )
        if not edges:
            return count

        stop = False
        for e in edges:
            starred_at = e.get("starredAt")
            if not starred_at:
                continue
            if starred_at < since_iso:
                stop = True
                break
            count += 1

        page_info = (
            (((body.get("data") or {}).get("repository") or {}).get("stargazers") or {}).get("pageInfo")
            or {}
        )
        if stop or not page_info.get("hasNextPage"):
            return count
        after = page_info.get("endCursor")
        if not after:
            return count


def get_hot_ai_repos(
    *,
    days: int = 14,
    topics: Optional[List[str]] = None,
    languages: Optional[List[str]] = None,
    limit: int = 20,
    base_url: str = "https://api.github.com",
    max_requests_per_minute: int = 30,
    timeout_sec: int = 20,
) -> List[Dict[str, Any]]:
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=max(1, int(days)))
    token = _get_token()
    limiter = RateLimiter(max_requests_per_minute)

    candidates = search_candidate_repos(
        topics=topics or [],
        languages=languages or [],
        since=since,
        limit=limit,
        base_url=base_url,
        limiter=limiter,
        timeout_sec=timeout_sec,
    )

    out: List[Tuple[Dict[str, Any], int]] = []
    for repo in candidates:
        full_name = repo.get("full_name")
        if not full_name:
            continue
        growth = _graphql_star_growth(
            full_name=full_name,
            since=since,
            token=token,
            limiter=limiter,
            timeout_sec=timeout_sec,
        )
        growth_v = int(growth) if growth is not None else int(repo.get("stargazers_count") or 0)
        out.append((repo, growth_v))

    out.sort(key=lambda x: x[1], reverse=True)
    return [_repo_to_item(r, star_growth=g) for r, g in out[:limit]]


from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict


Phase = Literal[
    "start",
    "github_fetch",
    "project_analyze",
    "news_fetch",
    "news_classify",
    "report",
    "done",
]


class RunParams(TypedDict, total=False):
    days: int
    github_topics: List[str]
    github_languages: List[str]
    github_limit: int
    news_days: int
    output_format: Literal["json", "markdown", "both"]


class AppState(TypedDict, total=False):
    phase: Phase
    next_node: str
    params: RunParams
    github_projects: List[Dict[str, Any]]
    project_analysis: List[Dict[str, Any]]
    news_items: List[Dict[str, Any]]
    news_categories: Dict[str, List[Dict[str, Any]]]
    report_json: Dict[str, Any]
    report_markdown: str
    errors: List[str]

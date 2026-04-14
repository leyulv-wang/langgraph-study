from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Tuple

from agent.state import AppState
from agent.utils.text import extract_keywords, normalize_whitespace, stable_dedupe


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _project_keywords(project: Dict[str, Any]) -> List[str]:
    parts = [
        project.get("full_name") or "",
        project.get("description") or project.get("summary") or "",
        " ".join(project.get("topics") or []),
        project.get("language") or "",
    ]
    return stable_dedupe(extract_keywords(" ".join([p for p in parts if p]), top_k=10))


def _news_keywords(item: Dict[str, Any]) -> List[str]:
    parts = [
        item.get("title") or "",
        item.get("summary") or "",
        " ".join(item.get("keywords") or []),
    ]
    return stable_dedupe(extract_keywords(" ".join([p for p in parts if p]), top_k=10))


def _overlap(a: List[str], b: List[str]) -> int:
    return len(set(a) & set(b))


def _top_related_news(
    *,
    project: Dict[str, Any],
    news: List[Dict[str, Any]],
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    pk = _project_keywords(project)
    scored: List[Tuple[int, Dict[str, Any]]] = []
    for it in news:
        nk = _news_keywords(it)
        s = _overlap(pk, nk)
        if s <= 0:
            continue
        scored.append((s, it))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [it for _, it in scored[:top_k]]


def _md_escape(s: str) -> str:
    return (s or "").replace("\n", " ").replace("|", "\\|")


def build_report(state: AppState) -> Dict[str, Any]:
    params = state.get("params") or {}
    projects = state.get("github_projects") or []
    analysis = state.get("project_analysis") or []
    news = state.get("news_items") or []
    news_categories = state.get("news_categories") or {}

    top_projects = projects[: min(10, len(projects))]
    top_analysis = analysis[: min(10, len(analysis))]

    related_map: Dict[str, List[Dict[str, Any]]] = {}
    for p in top_projects:
        key = p.get("full_name") or ""
        related_map[key] = _top_related_news(project=p, news=news, top_k=3)

    report_json: Dict[str, Any] = {
        "generated_at": _now_iso(),
        "params": params,
        "github": {
            "projects": projects,
            "analysis": analysis,
            "related_news": related_map,
        },
        "news": {
            "items": news,
            "categories": news_categories,
        },
    }

    lines: List[str] = []
    lines.append("# AI Weekly Brief")
    lines.append("")
    lines.append(f"- 生成时间：{report_json['generated_at']}")
    lines.append(f"- 时间窗口：近 {int(params.get('days', 14))} 天")
    lines.append("")
    lines.append("## GitHub 热门 AI 项目（按增长/热度）")
    lines.append("")
    lines.append("| 项目 | Stars | 近窗增长 | 语言 | 简介 |")
    lines.append("| --- | ---: | ---: | --- | --- |")
    for p in top_projects:
        lines.append(
            f"| [{_md_escape(p.get('full_name') or '')}]({_md_escape(p.get('html_url') or '')}) "
            f"| {int(p.get('stars') or 0)} "
            f"| {int(p.get('star_growth') or 0)} "
            f"| {_md_escape(p.get('language') or '')} "
            f"| {_md_escape(normalize_whitespace(p.get('description') or ''))} |"
        )
    lines.append("")

    lines.append("## 项目质量评估（Top 10）")
    lines.append("")
    lines.append("| 项目 | 评分 | Stars | Forks | Issues | Archived |")
    lines.append("| --- | ---: | ---: | ---: | ---: | --- |")
    for a in top_analysis:
        m = a.get("metrics") or {}
        lines.append(
            f"| [{_md_escape(a.get('full_name') or '')}]({_md_escape(a.get('url') or '')}) "
            f"| {a.get('score', 0)} "
            f"| {int(m.get('stars') or 0)} "
            f"| {int(m.get('forks') or 0)} "
            f"| {int(m.get('open_issues') or 0)} "
            f"| {bool(m.get('archived'))} |"
        )
    lines.append("")

    lines.append("## AI 新闻（按分类）")
    lines.append("")
    for cat, items in sorted(news_categories.items(), key=lambda x: x[0]):
        lines.append(f"### {cat}（{len(items)}）")
        for it in items[:10]:
            lines.append(
                f"- [{_md_escape(it.get('title') or '')}]({_md_escape(it.get('url') or '')}) "
                f"({_md_escape(it.get('source') or '')})"
            )
        lines.append("")

    lines.append("## 项目与新闻关联（Top 项目）")
    lines.append("")
    for p in top_projects:
        key = p.get("full_name") or ""
        rel = related_map.get(key) or []
        lines.append(f"### {key}")
        if not rel:
            lines.append("- 未找到明显关联新闻")
            lines.append("")
            continue
        for it in rel:
            lines.append(f"- [{_md_escape(it.get('title') or '')}]({_md_escape(it.get('url') or '')})")
        lines.append("")

    report_md = "\n".join(lines).strip() + "\n"

    return {"report_json": report_json, "report_markdown": report_md}


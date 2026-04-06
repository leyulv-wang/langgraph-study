from __future__ import annotations

from typing import Any, Dict, List, Tuple

from agent.state import AppState


def _safe_int(v: Any) -> int:
    try:
        return int(v)
    except Exception:
        return 0


def _score(repo: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    stars = _safe_int(repo.get("stars"))
    forks = _safe_int(repo.get("forks"))
    issues = _safe_int(repo.get("open_issues"))
    growth = repo.get("star_growth")
    growth_v = _safe_int(growth) if growth is not None else stars

    issues_penalty = 0.0
    if stars > 0:
        issues_penalty = min(1.0, issues / max(1, stars / 100))

    archived_penalty = 1.0 if repo.get("archived") else 0.0
    score = (growth_v * 1.2 + stars * 0.2 + forks * 0.3) * (1.0 - 0.15 * issues_penalty) * (
        1.0 - 0.6 * archived_penalty
    )

    metrics = {
        "stars": stars,
        "forks": forks,
        "open_issues": issues,
        "star_growth": growth_v,
        "archived": bool(repo.get("archived")),
        "language": repo.get("language") or "",
    }
    return float(score), metrics


def project_analyze(state: AppState) -> Dict[str, Any]:
    projects = state.get("github_projects") or []
    analysis: List[Dict[str, Any]] = []
    for repo in projects:
        s, metrics = _score(repo)
        analysis.append(
            {
                "full_name": repo.get("full_name"),
                "url": repo.get("html_url"),
                "score": round(s, 3),
                "metrics": metrics,
                "summary": repo.get("description") or "",
            }
        )
    analysis.sort(key=lambda x: x.get("score", 0), reverse=True)
    return {"project_analysis": analysis}


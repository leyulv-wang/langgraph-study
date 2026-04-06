from __future__ import annotations

import traceback
from typing import Any, Callable, Dict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from agent.agents.coordinator import coordinator
from agent.agents.github_fetch import github_fetch
from agent.agents.news_classifier import news_classify
from agent.agents.news_fetch import news_fetch
from agent.agents.project_analyzer import project_analyze
from agent.agents.report_aggregator import build_report
from agent.state import AppState


def _append_error(state: AppState, msg: str) -> Dict[str, Any]:
    errors = list(state.get("errors") or [])
    errors.append(msg)
    return {"errors": errors}


def _safe(node_name: str, fn: Callable[[AppState], Dict[str, Any]]):
    def wrapped(state: AppState, runtime: Runtime | None = None) -> Dict[str, Any]:
        try:
            return fn(state)
        except Exception:
            msg = f"{node_name}: {traceback.format_exc(limit=2)}"
            return _append_error(state, msg)

    return wrapped


builder = StateGraph(AppState)
builder.add_node("coordinator", coordinator)
builder.add_node("github_fetch", _safe("github_fetch", github_fetch))
builder.add_node("project_analyze", _safe("project_analyze", project_analyze))
builder.add_node("news_fetch", _safe("news_fetch", news_fetch))
builder.add_node("news_classify", _safe("news_classify", news_classify))
builder.add_node("report", _safe("report", build_report))

builder.add_edge(START, "coordinator")
builder.add_edge("github_fetch", "coordinator")
builder.add_edge("project_analyze", "coordinator")
builder.add_edge("news_fetch", "coordinator")
builder.add_edge("news_classify", "coordinator")
builder.add_edge("report", "coordinator")
builder.add_conditional_edges(
    "coordinator",
    lambda s: s.get("next_node", "__end__"),
    {
        "github_fetch": "github_fetch",
        "project_analyze": "project_analyze",
        "news_fetch": "news_fetch",
        "news_classify": "news_classify",
        "report": "report",
        "__end__": END,
    },
)

graph = builder.compile(name="multi_agent_reporter")

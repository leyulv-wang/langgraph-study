from __future__ import annotations

from agent.state import AppState


def coordinator(state: AppState):
    phase = state.get("phase", "start")

    if phase == "start":
        return {"phase": "github_fetch", "next_node": "github_fetch"}
    if phase == "github_fetch":
        return {"phase": "project_analyze", "next_node": "project_analyze"}
    if phase == "project_analyze":
        return {"phase": "news_fetch", "next_node": "news_fetch"}
    if phase == "news_fetch":
        return {"phase": "news_classify", "next_node": "news_classify"}
    if phase == "news_classify":
        return {"phase": "report", "next_node": "report"}
    if phase == "report":
        return {"phase": "done", "next_node": "__end__"}
    return {"phase": "done", "next_node": "__end__"}

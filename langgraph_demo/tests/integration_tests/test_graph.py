import pytest

from agent import graph

pytestmark = pytest.mark.anyio


async def test_multi_agent_report_smoke(monkeypatch) -> None:
    from agent.agents import github_fetch as gh_mod
    from agent.agents import news_fetch as news_mod

    def fake_hot_repos(**kwargs):
        return [
            {
                "full_name": "acme/awesome-ai",
                "html_url": "https://github.com/acme/awesome-ai",
                "description": "AI agent framework",
                "language": "Python",
                "topics": ["ai", "agents"],
                "stars": 1234,
                "forks": 56,
                "open_issues": 7,
                "archived": False,
                "star_growth": 120,
                "updated_at": "2026-04-01T00:00:00Z",
            }
        ]

    def fake_news(**kwargs):
        return [
            {
                "id": "n1",
                "source": "Tech",
                "title": "New agent framework released",
                "url": "https://example.com/news/1",
                "published_at": "2026-04-01T00:00:00+00:00",
                "content": "An agentic AI framework for workflows.",
                "keywords": ["agent", "workflow"],
                "summary": "An agentic AI framework for workflows.",
            }
        ]

    monkeypatch.setattr(gh_mod, "get_hot_ai_repos", fake_hot_repos)
    monkeypatch.setattr(news_mod, "fetch_ai_news", fake_news)

    res = await graph.ainvoke(
        {
            "phase": "start",
            "params": {"days": 14, "github_limit": 5, "output_format": "markdown"},
        }
    )
    assert "report_markdown" in res
    assert "GitHub 热门 AI 项目" in res["report_markdown"]

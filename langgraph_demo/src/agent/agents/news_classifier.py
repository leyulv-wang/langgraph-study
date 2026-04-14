from __future__ import annotations

from typing import Any, Dict, List

from agent.state import AppState


_CATEGORIES: Dict[str, List[str]] = {
    "Agent": ["agent", "agents", "agentic", "workflow", "autonomous", "multi-agent", "智能体", "代理", "工作流"],
    "LLM": ["llm", "language model", "transformer", "qwen", "gpt", "claude", "gemini", "大模型", "模型"],
    "RAG": ["rag", "retrieval", "vector", "embedding", "chroma", "检索", "向量"],
    "Multimodal": ["multimodal", "image", "video", "audio", "vision", "扩散", "多模态", "图像", "视频", "音频"],
    "Robotics": ["robot", "robotics", "embodied", "humanoid", "具身", "机器人"],
    "Research": ["arxiv", "paper", "benchmark", "dataset", "论文", "基准", "数据集"],
    "Industry": ["nvidia", "openai", "anthropic", "google", "meta", "microsoft", "投资", "发布", "企业"],
    "Policy": ["regulation", "policy", "law", "legal", "governance", "合规", "监管", "法律", "治理"],
}


def _classify(text: str) -> List[str]:
    t = (text or "").lower()
    hits: List[str] = []
    for cat, keys in _CATEGORIES.items():
        for k in keys:
            if k.lower() in t:
                hits.append(cat)
                break
    return hits or ["Other"]


def news_classify(state: AppState) -> Dict[str, Any]:
    items = state.get("news_items") or []
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for it in items:
        text = f"{it.get('title','')} {it.get('summary','')} {' '.join(it.get('keywords') or [])}"
        cats = _classify(text)
        it2 = {**it, "categories": cats}
        for c in cats:
            buckets.setdefault(c, []).append(it2)

    for c, lst in buckets.items():
        lst.sort(key=lambda x: x.get("published_at") or "", reverse=True)
        buckets[c] = lst

    return {"news_categories": buckets}


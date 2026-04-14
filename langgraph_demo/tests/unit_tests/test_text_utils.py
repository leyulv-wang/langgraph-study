from agent.utils.text import extract_keywords, normalize_whitespace, simple_summary, stable_dedupe


def test_normalize_whitespace() -> None:
    assert normalize_whitespace("a \n b\tc") == "a b c"


def test_extract_keywords() -> None:
    kws = extract_keywords("Agentic AI agents workflow workflow", top_k=3)
    assert "workflow" in kws


def test_simple_summary() -> None:
    s = simple_summary("第一句。第二句。第三句。", max_sentences=2)
    assert s.count("。") == 2


def test_stable_dedupe() -> None:
    assert stable_dedupe(["a", "a", "b"]) == ["a", "b"]


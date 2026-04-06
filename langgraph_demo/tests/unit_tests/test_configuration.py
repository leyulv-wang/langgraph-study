from agent.graph import graph


def test_graph_is_compiled() -> None:
    assert hasattr(graph, "invoke")
    assert callable(graph.invoke)

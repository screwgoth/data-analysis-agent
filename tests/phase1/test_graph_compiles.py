"""Unit: the analysis graph compiles without any env vars / LLM key."""


def test_graph_compiles():
    from graph.agent import agentic_ai

    assert agentic_ai is not None


def test_expected_nodes_present():
    from graph.agent import agentic_ai

    nodes = set(agentic_ai.get_graph().nodes.keys())
    for expected in (
        "plan",
        "write_code",
        "execute_local",
        "reflect",
        "answer",
        "finalize",
        "handle_error",
    ):
        assert expected in nodes

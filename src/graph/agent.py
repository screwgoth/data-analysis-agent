from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import (
    node_plan,
    node_write_code,
    node_execute_local,
    node_reflect,
    node_answer,
    node_suggest,
    node_finalize,
    node_handle_error,
)
from graph.edges import (
    route_after_plan,
    route_after_reflect,
    after_write_code,
    after_execute,
    after_answer,
)


def _build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("plan", node_plan)
    graph.add_node("write_code", node_write_code)
    graph.add_node("execute_local", node_execute_local)
    graph.add_node("reflect", node_reflect)
    graph.add_node("answer", node_answer)
    graph.add_node("suggest", node_suggest)
    graph.add_node("finalize", node_finalize)
    graph.add_node("handle_error", node_handle_error)

    graph.set_entry_point("plan")

    graph.add_conditional_edges(
        "plan",
        route_after_plan,
        {
            "handle_error": "handle_error",
            "finalize": "finalize",
            "write_code": "write_code",
        },
    )
    graph.add_conditional_edges(
        "write_code",
        after_write_code,
        {"handle_error": "handle_error", "execute_local": "execute_local"},
    )
    graph.add_conditional_edges(
        "execute_local",
        after_execute,
        {"handle_error": "handle_error", "reflect": "reflect"},
    )
    graph.add_conditional_edges(
        "reflect",
        route_after_reflect,
        {"write_code": "write_code", "answer": "answer"},
    )
    graph.add_conditional_edges(
        "answer",
        after_answer,
        {"handle_error": "handle_error", "suggest": "suggest"},
    )
    graph.add_edge("suggest", "finalize")
    graph.add_edge("finalize", END)
    graph.add_edge("handle_error", END)

    return graph.compile()


agentic_ai = _build_graph()

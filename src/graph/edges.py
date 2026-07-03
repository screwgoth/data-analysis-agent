from graph.state import AgentState


def err_or(target: str):
    """Return a router that goes to handle_error on state["error"], else target."""

    def _router(state: AgentState) -> str:
        if state.get("error"):
            return "handle_error"
        return target

    return _router


# Prebuilt routers for the linear error branches.
_after_write_code = err_or("execute_local")
_after_execute = err_or("reflect")
_after_answer = err_or("suggest")


def after_write_code(state: AgentState) -> str:
    return _after_write_code(state)


def after_execute(state: AgentState) -> str:
    return _after_execute(state)


def after_answer(state: AgentState) -> str:
    return _after_answer(state)


def route_after_plan(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    if state.get("clarifying_question"):
        return "finalize"
    return "write_code"


def route_after_reflect(state: AgentState) -> str:
    done = state.get("reflect_done", True)
    if not done and state.get("current_step", 0) < state.get("max_steps", 6):
        return "write_code"
    return "answer"

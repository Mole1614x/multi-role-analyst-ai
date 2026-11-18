import re
from collections.abc import Callable
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

from app.agents.workflow import PlannedStep


class PlanState(TypedDict, total=False):
    steps: list[dict]
    completed_steps: list[dict]
    pending_approval: int | None


def draft_steps(objective: str, approve_external: bool) -> list[PlannedStep]:
    prompts = [
        clause.strip(" ,.")
        for clause in re.split(r"\s+(?:and\s+)?then\s+|\r?\n+", objective, flags=re.IGNORECASE)
        if clause.strip(" ,.")
    ]
    if not 2 <= len(prompts) <= 6 or any(len(clause) < 3 for clause in prompts):
        raise ValueError("Describe two to six analysis requests separated by ‘then’ or line breaks.")
    return [
        PlannedStep(prompt=prompt, approve_external=approve_external, require_approval=index == 0)
        for index, prompt in enumerate(prompts)
    ]


def run_plan(
    request_steps: list[PlannedStep],
    saved: dict,
    approved_step: int | None,
    execute: Callable[[int, PlannedStep, dict | None], dict],
    persist: Callable[[dict], None],
) -> dict:
    plan = [
        entry.model_dump(mode="json", exclude={"approve_external"}) | {"external": entry.approve_external}
        for entry in request_steps
    ]
    initial = PlanState(steps=plan, completed_steps=saved.get("completed_steps", []), pending_approval=None)

    def review(state: PlanState):
        index = len(state["completed_steps"])
        step = request_steps[index]
        needs_approval = step.require_approval or step.approve_external
        if needs_approval and approved_step != index:
            persist(dict(state) | {"pending_approval": index})
            return {"pending_approval": index}
        return {"pending_approval": None}

    def execute_step(state: PlanState):
        completed = state["completed_steps"]
        index = len(completed)
        prior = completed[-1] if completed else None
        result = execute(index, request_steps[index], prior)
        update = {"completed_steps": [*completed, result], "pending_approval": None}
        persist(dict(state) | update)
        return update

    graph = StateGraph(PlanState)
    graph.add_node("review", review)
    graph.add_node("execute_step", execute_step)
    graph.add_conditional_edges(
        START, lambda s: len(s["completed_steps"]) < len(plan), {True: "review", False: END}
    )
    graph.add_conditional_edges(
        "review", lambda s: s["pending_approval"] is None, {True: "execute_step", False: END}
    )
    graph.add_conditional_edges(
        "execute_step", lambda s: len(s["completed_steps"]) < len(plan), {True: "review", False: END}
    )
    with tracing_context(enabled=False):
        state = graph.compile().invoke(initial, {"recursion_limit": 16})
    if state["pending_approval"] is not None:
        return state
    last = state["completed_steps"][-1]
    chart = next((entry["chart"] for entry in reversed(state["completed_steps"]) if "chart" in entry), None)
    source = next(
        (entry["source"] for entry in reversed(state["completed_steps"]) if entry.get("source")), None
    )
    return (
        last
        | state
        | {
            "summary": f"{len(plan)} workflow steps completed. {last['summary']}",
            "plan": last["plan"] | {"objective": saved.get("objective") or last["plan"]["objective"]},
            "chart": chart,
            "source": source,
        }
    )

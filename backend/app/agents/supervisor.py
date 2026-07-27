"""
F7 — Supervisor / Router.

The "manager" agent: reads the question and what's been collected so far,
and decides which specialist runs next — or that enough has been gathered
to generate a final answer.

Done when: for a SQL question it routes to `data`; for a doc question to
`retriever`; it eventually chooses `finish`.
"""
from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import get_llm
from app.core.state import AgentState

Route = Literal["retriever", "web", "data", "code", "finish"]

# Hard cap on specialist calls per question — regardless of what the LLM
# router decides, we force `finish` past this point. Without this, a
# router that never settles (bouncing between agents on an ambiguous
# question) can hit LangGraph's recursion_limit and crash the whole run.
MAX_AGENT_CALLS = 5


class RouteDecision(BaseModel):
    next: Route = Field(
        description=(
            "Which agent should run next. "
            "'retriever' for questions answerable from internal documents. "
            "'web' for questions needing current/external information. "
            "'data' for questions needing a database lookup/count. "
            "'code' for questions needing a calculation. "
            "'finish' once enough evidence has been gathered to answer."
        )
    )
    reasoning: str = Field(description="One short sentence explaining the choice.")


def _agent_call_count(steps: list) -> int:
    specialist_markers = ("retriever", "web", "data(sql)", "code", "web-skipped", "web-error", "data(sql)-refused", "data(sql)-error")
    return sum(1 for s in steps if s in specialist_markers)


_STEP_MARKER = {"retriever": "retriever", "web": "web", "data": "data(sql)", "code": "code"}


def _already_ran(agent: str, steps: list) -> bool:
    marker = _STEP_MARKER.get(agent)
    return any(s == marker or s.startswith(f"{marker}-") for s in steps)


def supervisor(state: AgentState) -> dict:
    steps_so_far = state.get("steps", [])

    if _agent_call_count(steps_so_far) >= MAX_AGENT_CALLS:
        return {
            "plan": "finish",
            "steps": steps_so_far + ["supervisor->finish(cap)"],
        }

    llm = get_llm().with_structured_output(RouteDecision)

    collected = {
        "documents": state.get("documents", []),
        "web_result": state.get("web_result"),
        "sql_result": state.get("sql_result"),
        "code_result": state.get("code_result"),
    }

    memory = state.get("memory_context", [])
    memory_block = ("Relevant past turns:\n" + "\n---\n".join(memory) + "\n\n") if memory else ""

    prompt = (
        f"{memory_block}"
        f"Question: {state['question']}\n"
        f"Steps taken so far: {steps_so_far}\n"
        f"Evidence collected so far: {collected}\n\n"
        f"Routing guidance:\n"
        f"- 'retriever' is for questions about THIS company's internal data "
        f"(churn reasons, product notes, internal reports) — try this FIRST "
        f"for any question that sounds like it's about our company's own "
        f"history, customers, or documents.\n"
        f"- 'web' is ONLY for questions needing current external/public "
        f"information that would never be in our internal documents (e.g. "
        f"industry news, a definition, a public fact).\n"
        f"- 'data' is for questions needing an exact count/number from the database.\n"
        f"- 'code' is for questions needing a calculation.\n"
        f"- If the question refers back to something in the past turns (e.g. "
        f"'and the previous quarter?'), use that context to understand what's "
        f"being asked.\n\n"
        f"Decide the next agent to run, or 'finish' if there's enough evidence "
        f"to answer the question fully."
    )
    decision = llm.invoke(prompt)
    chosen = decision.next

    # Hard override: never let the model re-route to a specialist that
    # already ran (relying on the prompt alone wasn't reliable enough in
    # testing — see Phase 4 error analysis). Fall back to the next untried
    # agent in a fixed preference order, or finish if all have been tried.
    if chosen != "finish" and _already_ran(chosen, steps_so_far):
        fallback_order = ["retriever", "data", "code", "web"]
        untried = [a for a in fallback_order if not _already_ran(a, steps_so_far)]
        chosen = untried[0] if untried else "finish"

    just_revised = steps_so_far and steps_so_far[-1] == "critic:revise"
    if chosen == "finish" and just_revised:
        fallback_order = ["data", "retriever", "code", "web"]
        untried = [a for a in fallback_order if not _already_ran(a, steps_so_far)]
        if untried:
            chosen = untried[0]

    return {
        "plan": chosen,
        "steps": steps_so_far + [f"supervisor->{chosen}"],
    }


if __name__ == "__main__":
    from app.core.config import settings
    from app.core.state import new_state

    settings.validate()

    for q in [
        "How many customers churned in Q3?",
        "Why did Enterprise customers churn in Q3?",
        "What is 15% of 480?",
    ]:
        state = new_state(q)
        result = supervisor(state)
        print(f"Q: {q}\n  -> routed to: {result['plan']}\n")
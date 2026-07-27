"""
F7 — Supervisor / Router.
"""
from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import get_llm
from app.core.state import AgentState

Route = Literal["retriever", "web", "data", "code", "finish"]


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


def supervisor(state: AgentState) -> dict:
    llm = get_llm().with_structured_output(RouteDecision)

    collected = {
        "documents": state.get("documents", []),
        "web_result": state.get("web_result"),
        "sql_result": state.get("sql_result"),
        "code_result": state.get("code_result"),
    }

    prompt = (
        f"Question: {state['question']}\n"
        f"Steps taken so far: {state.get('steps', [])}\n"
        f"Evidence collected so far: {collected}\n\n"
        f"Decide the next agent to run, or 'finish' if there's enough evidence "
        f"to answer the question fully. Don't repeat an agent that already "
        f"produced a usable result unless it clearly failed."
    )
    decision = llm.invoke(prompt)

    return {
        "plan": decision.next,
        "steps": state.get("steps", []) + [f"supervisor->{decision.next}"],
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
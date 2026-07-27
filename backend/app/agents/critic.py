"""
F8 — Critic / Verifier.
"""
from pydantic import BaseModel, Field

from app.core.config import get_llm
from app.core.state import AgentState


class Verdict(BaseModel):
    ok: bool = Field(description="True if the answer is correct AND fully supported by the evidence.")
    reason: str = Field(description="One short sentence explaining the verdict.")


def critic(state: AgentState) -> dict:
    llm = get_llm().with_structured_output(Verdict)

    evidence = {
        "documents": state.get("documents", []),
        "web_result": state.get("web_result"),
        "sql_result": state.get("sql_result"),
        "code_result": state.get("code_result"),
        "past_turns_from_memory": state.get("memory_context", []),
    }

    prompt = (
        f"Question: {state['question']}\n"
        f"Evidence: {evidence}\n"
        f"Drafted answer: {state.get('answer')}\n\n"
        f"Is the answer correct AND fully supported by the evidence above? "
        f"Flag it as not ok if it states a fact the evidence doesn't contain, "
        f"or if it's missing something the evidence clearly provides."
    )
    verdict = llm.invoke(prompt)

    revisions = state.get("revisions", 0) + (0 if verdict.ok else 1)

    return {
        "revisions": revisions,
        "critic_reason": verdict.reason,
        "steps": state.get("steps", []) + [f"critic:{'ok' if verdict.ok else 'revise'}"],
    }


if __name__ == "__main__":
    from app.core.config import settings
    from app.core.state import new_state

    settings.validate()

    bad_state = new_state("How many customers churned in Q3?")
    bad_state["sql_result"] = "SELECT COUNT(*) FROM churn_events WHERE quarter = 'Q3';\n→ [(3,)]"
    bad_state["answer"] = "5 customers churned in Q3."
    print("Deliberately wrong answer:", critic(bad_state))

    good_state = new_state("How many customers churned in Q3?")
    good_state["sql_result"] = "SELECT COUNT(*) FROM churn_events WHERE quarter = 'Q3';\n→ [(3,)]"
    good_state["answer"] = "3 customers churned in Q3."
    print("Correct answer:", critic(good_state))
"""
Generate node — drafts an answer from gathered evidence.
"""
from app.core.config import get_llm
from app.core.state import AgentState


def generate(state: AgentState) -> dict:
    llm = get_llm()

    evidence_parts = []
    if state.get("documents"):
        evidence_parts.append("Documents:\n" + "\n---\n".join(state["documents"]))
    if state.get("web_result"):
        evidence_parts.append("Web search:\n" + state["web_result"])
    if state.get("sql_result"):
        evidence_parts.append("Database query:\n" + state["sql_result"])
    if state.get("code_result"):
        evidence_parts.append("Computation:\n" + state["code_result"])
    if state.get("memory_context"):
        evidence_parts.append("Relevant past turns:\n" + "\n---\n".join(state["memory_context"]))

    evidence = "\n\n".join(evidence_parts) or "(no evidence gathered)"

    prompt = (
        f"Question: {state['question']}\n\n"
        f"Evidence:\n{evidence}\n\n"
        f"Write a clear, direct answer using ONLY the evidence above. "
        f"If the evidence doesn't support a full answer, say what's missing."
    )
    answer = llm.invoke(prompt).content

    return {
        "answer": answer,
        "steps": state.get("steps", []) + ["generate"],
    }
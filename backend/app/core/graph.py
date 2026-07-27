"""
F9 — Supervisor graph (wiring).
"""
from langgraph.graph import END, StateGraph

from app.agents.code_agent import code_agent
from app.agents.critic import critic
from app.agents.data_agent import data_agent
from app.agents.generate import generate
from app.agents.retriever_agent import retriever_agent
from app.agents.supervisor import supervisor
from app.agents.web_agent import web_agent
from app.core.config import settings
from app.core.state import AgentState


def _route_from_supervisor(state: AgentState) -> str:
    plan = state.get("plan", "finish")
    return "generate" if plan == "finish" else plan


def _route_after_critic(state: AgentState) -> str:
    last_step = state.get("steps", [])[-1] if state.get("steps") else ""
    approved = last_step.endswith(":ok")
    if approved or state.get("revisions", 0) >= settings.MAX_REVISIONS:
        return "finish"
    return "revise"


def build_graph():
    g = StateGraph(AgentState)

    g.add_node("supervisor", supervisor)
    g.add_node("retriever", retriever_agent)
    g.add_node("web", web_agent)
    g.add_node("data", data_agent)
    g.add_node("code", code_agent)
    g.add_node("generate", generate)
    g.add_node("critic", critic)

    g.set_entry_point("supervisor")

    g.add_conditional_edges(
        "supervisor",
        _route_from_supervisor,
        {
            "retriever": "retriever",
            "web": "web",
            "data": "data",
            "code": "code",
            "generate": "generate",
        },
    )

    for agent_name in ["retriever", "web", "data", "code"]:
        g.add_edge(agent_name, "supervisor")

    g.add_edge("generate", "critic")

    g.add_conditional_edges(
        "critic",
        _route_after_critic,
        {"finish": END, "revise": "supervisor"},
    )

    return g.compile()


def run(question: str) -> AgentState:
    from app.core.state import new_state

    graph = build_graph()
    initial_state = new_state(question)
    final_state = graph.invoke(
        initial_state,
        config={"recursion_limit": settings.RECURSION_LIMIT},
    )
    return final_state


if __name__ == "__main__":
    settings.validate()

    question = "How many customers churned in Q3, and why?"
    result = run(question)

    print(f"Question: {question}\n")
    print(f"Answer:\n{result['answer']}\n")
    print("Trace:")
    for step in result["steps"]:
        print(f"  - {step}")
"""
F1 — Shared state.

One AgentState object flows through every node in the LangGraph graph.
Every agent (retriever, web, data, code), the supervisor, and the critic
read from and write to this same structure. This is what makes the
system a *team* instead of a pile of disconnected functions.
"""
from __future__ import annotations

from typing import List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    # the user's question for this turn
    question: str

    # relevant history pulled from long-term memory (F10), fed to the supervisor
    memory_context: List[str]

    # supervisor's routing decision for the current step: retriever|web|data|code|finish
    plan: str

    # results gathered from each specialist agent
    documents: List[str]          # retriever (F3)
    web_result: Optional[str]     # web agent (F4)
    sql_result: Optional[str]     # data/SQL agent (F5)
    code_result: Optional[str]    # code agent (F6)

    # the draft/final answer produced by the generate node
    answer: Optional[str]

    # critic bookkeeping (F8)
    revisions: int
    critic_reason: Optional[str]

    # trace of every step taken, e.g. ["supervisor->data", "data(sql)", "critic:ok"]
    # this is what F13 (streaming frontend) and F12 (Langfuse) surface to the user
    steps: List[str]


def new_state(question: str, memory_context: Optional[List[str]] = None) -> AgentState:
    """Build a fresh AgentState for a new turn."""
    return AgentState(
        question=question,
        memory_context=memory_context or [],
        plan="",
        documents=[],
        web_result=None,
        sql_result=None,
        code_result=None,
        answer=None,
        revisions=0,
        critic_reason=None,
        steps=[],
    )

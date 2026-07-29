"""
F13 (backend half) — API server.
"""
import json
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.config import settings
from app.core.graph import build_graph
from app.core.memory import add_turn, recall
from app.core.observability import flush, get_langfuse_handler
from app.core.state import new_state

app = FastAPI(title="Multi-Agent AI Analyst")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str
    use_memory: bool = True
    enabled_agents: Optional[List[str]] = None


# Human-readable line for each graph node. The frontend maps these to the
# coloured lanes on the execution rail, so keep the agent word in the text.
NODE_MESSAGES = {
    "supervisor": "Supervisor deciding next step...",
    "retriever": "Retriever searching documents...",
    "web": "Web agent searching the live web...",
    "data": "Data agent writing SQL...",
    "code": "Code agent running Python...",
    "generate": "Writing the final answer...",
    "critic": "Critic verifying the answer...",
}


def sse(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def as_source(doc: Any, index: int) -> Dict[str, Any]:
    """Turn one retrieved chunk into a card the frontend can render."""
    if isinstance(doc, dict):
        meta = doc.get("metadata") or {}
        text = doc.get("text") or doc.get("page_content") or doc.get("content") or ""
        return {
            "title": doc.get("title") or meta.get("title") or f"Passage {index + 1}",
            "file": doc.get("source") or meta.get("source") or meta.get("file") or "",
            "excerpt": text,
            "score": doc.get("score") or meta.get("score"),
        }

    text = str(doc)
    # first line often reads like a heading; use it when it's short enough
    head = text.strip().split("\n", 1)[0]
    title = head if 0 < len(head) <= 80 else f"Passage {index + 1}"
    return {"title": title, "file": "", "excerpt": text, "score": None}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask")
def ask(req: AskRequest):
    memory_context = recall(req.question) if req.use_memory else []
    graph = build_graph()
    initial_state = new_state(req.question, memory_context=memory_context)

    invoke_config = {"recursion_limit": settings.RECURSION_LIMIT}
    handler = get_langfuse_handler()
    if handler:
        invoke_config["callbacks"] = [handler]

    final_state = graph.invoke(initial_state, config=invoke_config)

    if handler:
        flush()
    if req.use_memory and final_state.get("answer"):
        add_turn(req.question, final_state["answer"])

    return {
        "answer": final_state.get("answer"),
        "steps": final_state.get("steps", []),
    }


@app.post("/ask/stream")
def ask_stream(req: AskRequest):
    def event_generator():
        memory_context = recall(req.question) if req.use_memory else []
        graph = build_graph()
        initial_state = new_state(req.question, memory_context=memory_context)

        invoke_config = {"recursion_limit": settings.RECURSION_LIMIT}
        handler = get_langfuse_handler()
        if handler:
            invoke_config["callbacks"] = [handler]

        merged_state = dict(initial_state)
        sent_docs = 0
        sent_sql: Optional[str] = None
        sent_code: Optional[str] = None
        last_revisions = 0

        for chunk in graph.stream(initial_state, config=invoke_config):
            for node_name, node_output in chunk.items():
                merged_state.update(node_output)

                # 1. progress line — supervisor's decision goes in one line
                plan = node_output.get("plan")
                if node_name == "supervisor" and plan:
                    message = (
                        "Supervisor finishing up..."
                        if plan == "finish"
                        else f"Supervisor routing to {plan}..."
                    )
                else:
                    message = NODE_MESSAGES.get(node_name, f"{node_name} running...")
                yield sse({"type": "status", "message": message, "node": node_name})

            

                # 3. retrieved passages -> SOURCES panel
                documents = merged_state.get("documents") or []
                if len(documents) > sent_docs:
                    yield sse({
                        "sources": [as_source(d, i) for i, d in enumerate(documents)]
                    })
                    sent_docs = len(documents)

                # 4. SQL -> SQL panel
                sql_result = merged_state.get("sql_result")
                if sql_result and sql_result != sent_sql:
                    yield sse({"sql": {"query": str(sql_result)}})
                    sent_sql = sql_result

                # 5. Python -> CODE panel
                code_result = merged_state.get("code_result")
                if code_result and code_result != sent_code:
                    yield sse({"code": {"language": "python", "code": str(code_result)}})
                    sent_code = code_result

                # 6. critic rejection starts a new branch
                reason = node_output.get("critic_reason")
                if node_name == "critic" and reason:
                    yield sse({"type": "status", "message": f"Critic sent it back: {reason}"})

        if handler:
            flush()

        answer = merged_state.get("answer")
        steps = merged_state.get("steps", [])
        if req.use_memory and answer:
            add_turn(req.question, answer)

        yield sse({"type": "final", "answer": answer, "steps": steps})

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    settings.validate()
    uvicorn.run(app, host="0.0.0.0", port=8000)
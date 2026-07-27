"""
F13 (backend half) — API server.
"""
import json

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
        for chunk in graph.stream(initial_state, config=invoke_config):
            for node_name, node_output in chunk.items():
                merged_state.update(node_output)
                payload = {"type": "step", "node": node_name}
                if "plan" in node_output:
                    payload["plan"] = node_output["plan"]
                yield f"data: {json.dumps(payload)}\n\n"

        if handler:
            flush()

        answer = merged_state.get("answer")
        steps = merged_state.get("steps", [])
        if req.use_memory and answer:
            add_turn(req.question, answer)

        yield f"data: {json.dumps({'type': 'final', 'answer': answer, 'steps': steps})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    settings.validate()
    uvicorn.run(app, host="0.0.0.0", port=8000)
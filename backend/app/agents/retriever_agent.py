"""
F3 — Retriever agent.
Runs similarity search against the Qdrant vector store built in F2.
"""
from app.core.config import settings
from app.core.ingestion import build_vector_store
from app.core.state import AgentState

TOP_K = 3


def retriever_agent(state: AgentState) -> dict:
    store = build_vector_store()
    results = store.similarity_search(state["question"], k=TOP_K)

    chunks = [doc.page_content.strip() for doc in results]

    return {
        "documents": state.get("documents", []) + chunks,
        "steps": state.get("steps", []) + ["retriever"],
    }


if __name__ == "__main__":
    from app.core.state import new_state

    settings.validate()
    test_state = new_state("Why did Enterprise customers churn in Q3?")
    result = retriever_agent(test_state)
    print(f"Retrieved {len(result['documents'])} chunk(s):\n")
    for i, chunk in enumerate(result["documents"], 1):
        print(f"--- chunk {i} ---")
        print(chunk[:300])
        print()
"""
F10 — Long-term memory.
"""
from app.core.config import settings
from app.core.ingestion import build_vector_store
from langchain_core.documents import Document

TOP_K = 3


def _memory_store():
    return build_vector_store(collection_name=settings.QDRANT_MEMORY_COLLECTION)


def add_turn(question: str, answer: str) -> None:
    store = _memory_store()
    text = f"Q: {question}\nA: {answer}"
    store.add_documents([Document(page_content=text, metadata={"question": question})])


def recall(question: str, k: int = TOP_K) -> list[str]:
    store = _memory_store()
    try:
        results = store.similarity_search(question, k=k)
    except Exception:
        return []
    return [doc.page_content for doc in results]


if __name__ == "__main__":
    settings.validate()

    add_turn(
        "How many customers churned in Q3?",
        "3 customers churned in Q3.",
    )

    past = recall("What about the previous quarter?")
    print(f"Recalled {len(past)} past turn(s) for the follow-up:\n")
    for p in past:
        print(p)
        print()
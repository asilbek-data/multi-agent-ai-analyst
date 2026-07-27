"""
Quick manual check for Phase 1's "Done when" criteria:
  F1 - shared state defined & used; keys load from .env
  F2 - ingestion works; similarity search returns relevant chunks

Run: python verify_phase1.py
"""
from app.core.config import settings
from app.core.ingestion import ingest, build_vector_store
from app.core.state import new_state


def main():
    settings.validate()
    print("F1 check — config loaded, OPENAI_API_KEY present:", bool(settings.OPENAI_API_KEY))

    state = new_state("How many customers churned in Q3 and why?")
    print("F1 check — AgentState created with keys:", list(state.keys()))

    n = ingest()
    if n == 0:
        print("F2 check — SKIPPED (no documents found in backend/data).")
        return

    store = build_vector_store()
    query = "Why did Enterprise customers churn in Q3?"
    results = store.similarity_search(query, k=2)
    print(f"\nF2 check — similarity_search('{query}') returned {len(results)} chunk(s):\n")
    for i, doc in enumerate(results, 1):
        print(f"--- chunk {i} (source: {doc.metadata.get('source')}) ---")
        print(doc.page_content.strip()[:300])
        print()


if __name__ == "__main__":
    main()

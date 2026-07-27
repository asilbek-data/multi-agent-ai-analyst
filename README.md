# Multi-Agent AI Analyst

A supervisor agent that routes to specialist agents (document retriever, web
search, SQL/data, code execution), with a critic that verifies the answer
before it's returned. Built with LangGraph, OpenAI, and Qdrant.

Successor to the earlier single-agent RAG / Agentic RAG project — this one
is a *team* of agents instead of one agent with a fallback.

## Stack

- **LLM + embeddings:** OpenAI (`gpt-4o-mini` + `text-embedding-3-small`)
- **Vector store:** Qdrant (local embedded by default, Qdrant Cloud optional)
- **Orchestration:** LangGraph
- **Database (F5):** SQLite via SQLAlchemy (read-only guard)
- **Code execution (F6):** sandboxed Python REPL
- **Web search (F4, optional):** Tavily
- **Evaluation (F11):** RAGAS + LLM-as-judge
- **Observability (F12, optional):** Langfuse
- **Frontend (F13):** Next.js, streams the live agent trace
- **Deploy (F14):** backend on Render, frontend on Vercel

## Build order (5 phases, 14 features)

1. **Foundation** — F1 shared state & config, F2 ingestion + vector store ✅ done
2. **Specialist agents** (build & test each alone) — F3 retriever, F4 web, F5 data/SQL, F6 code
3. **Orchestration** — F7 supervisor/router, F8 critic, F9 graph wiring
4. **Memory & Evaluation** — F10 long-term memory, F11 RAGAS + LLM-judge harness
5. **Observability, Frontend & Deploy** — F12 Langfuse, F13 streaming frontend, F14 deployment

Each phase depends on the one before it — there's nothing to route to until
the specialist agents exist, and nothing to evaluate until the graph runs
end-to-end.

## Setup

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in OPENAI_API_KEY at minimum
```

## Phase 1 status (done)

- `app/core/state.py` — `AgentState` TypedDict, shared across every node
- `app/core/config.py` — loads keys from `.env`; `get_llm()` / `get_embeddings()`
  are the single place every agent gets its OpenAI clients from
- `app/core/ingestion.py` — loads `.txt`/`.md` files from `backend/data/`,
  chunks them, embeds with OpenAI, upserts into Qdrant
- `backend/data/sample_company_notes.txt` — sample doc to test ingestion against
- `verify_phase1.py` — run this to confirm F1 + F2's "Done when" criteria:

```bash
cd backend
python verify_phase1.py
```

Expect: config loads, an `AgentState` is created, ingestion reports chunks
ingested, and a similarity search for "Why did Enterprise customers churn in
Q3?" returns the Q3 churn chunk.

## Next: Phase 2

Build and test each specialist agent alone before wiring them together:
F3 (retriever) → F4 (web) → F5 (data/SQL) → F6 (code).

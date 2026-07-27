"""
F4 — Web agent.
Searches the web via Tavily. Skips gracefully if no API key is set.
"""
from app.core.config import settings
from app.core.state import AgentState

MAX_RESULTS = 3


def web_agent(state: AgentState) -> dict:
    if not settings.TAVILY_API_KEY:
        return {
            "web_result": "SKIPPED — no TAVILY_API_KEY configured.",
            "steps": state.get("steps", []) + ["web-skipped"],
        }

    from tavily import TavilyClient

    client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    try:
        response = client.search(query=state["question"], max_results=MAX_RESULTS)
    except Exception as exc:
        return {
            "web_result": f"ERROR calling Tavily: {exc}",
            "steps": state.get("steps", []) + ["web-error"],
        }

    results = response.get("results", [])
    summary = "\n\n".join(
        f"{r.get('title', '')}\n{r.get('content', '')[:400]}\nSource: {r.get('url', '')}"
        for r in results
    )

    return {
        "web_result": summary or "No results found.",
        "steps": state.get("steps", []) + ["web"],
    }


if __name__ == "__main__":
    from app.core.state import new_state

    settings.validate()
    test_state = new_state("What is LangGraph used for?")
    result = web_agent(test_state)
    print(result["web_result"])
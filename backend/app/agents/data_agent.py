"""
F5 — Data/SQL agent.

Writes a SQL query from a plain-English question, runs it against the
read-only database, and returns the result.
"""
import re

from langchain_community.utilities import SQLDatabase

from app.core.config import get_llm, settings
from app.core.state import AgentState

_FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|create|attach|pragma)\b", re.IGNORECASE)


def _get_db() -> SQLDatabase:
    return SQLDatabase.from_uri(settings.DATABASE_URL)


def _extract_sql(raw: str) -> str:
    text = raw.strip()
    text = re.sub(r"^```(sql)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def _is_read_only(sql: str) -> bool:
    stripped = sql.strip().lower()
    if not stripped.startswith("select"):
        return False
    if _FORBIDDEN.search(sql):
        return False
    return True


def data_agent(state: AgentState) -> dict:
    db = _get_db()
    llm = get_llm()

    prompt = (
        f"You are a SQLite expert. Given this schema:\n{db.get_table_info()}\n\n"
        f"Write ONE SQLite SELECT query to answer: {state['question']}\n"
        f"Return ONLY the raw SQL, no markdown, no explanation."
    )
    raw = llm.invoke(prompt).content
    sql = _extract_sql(raw)

    if not _is_read_only(sql):
        return {
            "sql_result": f"REFUSED — query was not a safe read-only SELECT: {sql}",
            "steps": state.get("steps", []) + ["data(sql)-refused"],
        }

    try:
        rows = db.run(sql)
    except Exception as exc:
        return {
            "sql_result": f"SQL error running `{sql}`: {exc}",
            "steps": state.get("steps", []) + ["data(sql)-error"],
        }

    return {
        "sql_result": f"{sql}\n→ {rows}",
        "steps": state.get("steps", []) + ["data(sql)"],
    }


if __name__ == "__main__":
    from app.core.state import new_state

    settings.validate()
    test_state = new_state("How many customers churned in Q3?")
    result = data_agent(test_state)
    print(result["sql_result"])
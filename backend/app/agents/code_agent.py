"""
F6 — Code agent.

Writes and executes Python for calculations, aggregation, or derived
numbers the LLM would otherwise guess at. Runs in a *separate process*
with a hard runtime cap — never execute model-written code inline on the
main server process.

Test this agent alone before wiring it into the supervisor graph.

Done when: a math/aggregation question returns the correct computed answer.

Watch out: sandboxed with a runtime cap — a subprocess timeout, not just
a try/except. An infinite loop in generated code must not hang the server.
"""
import re
import subprocess
import sys

from app.core.config import get_llm, settings
from app.core.state import AgentState

RUNTIME_CAP_SECONDS = 5


def _extract_code(raw: str) -> str:
    """Strip markdown code fences the model might add despite instructions."""
    text = raw.strip()
    text = re.sub(r"^```(python)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def _run_sandboxed(code: str, timeout: int = RUNTIME_CAP_SECONDS) -> str:
    """
    Run `code` in a fresh subprocess with a hard timeout. This is the
    runtime cap the guide calls out — an infinite loop in generated code
    gets killed instead of hanging the process that's serving requests.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"ERROR: code exceeded the {timeout}s runtime cap and was killed."

    if proc.returncode != 0:
        return f"ERROR running generated code:\n{proc.stderr.strip()[-500:]}"

    output = proc.stdout.strip()
    return output if output else "(code ran with no printed output)"


def code_agent(state: AgentState) -> dict:
    llm = get_llm()

    prompt = (
        f"Write Python code to answer this question: {state['question']}\n"
        f"The code must print() the final result. Return ONLY the raw Python "
        f"code, no markdown, no explanation. Do not read/write files or use "
        f"network access."
    )
    raw = llm.invoke(prompt).content
    code = _extract_code(raw)

    output = _run_sandboxed(code)

    return {
        "code_result": f"{code}\n→ {output}",
        "steps": state.get("steps", []) + ["code"],
    }


if __name__ == "__main__":
    from app.core.state import new_state

    settings.validate()
    test_state = new_state(
        "If a company has 120 customers and loses 8% of them per quarter, "
        "how many customers remain after 3 quarters? Round to the nearest whole number."
    )
    result = code_agent(test_state)
    print(result["code_result"])
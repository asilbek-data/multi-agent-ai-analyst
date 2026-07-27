"""
F11 — Evaluation harness (LLM-as-judge).
Run: python -m app.core.evaluate
"""
import json
import time

from pydantic import BaseModel, Field

from app.core.config import get_llm, settings
from app.core.eval_dataset import EVAL_QUESTIONS
from app.core.graph import run


class JudgeScore(BaseModel):
    correctness: float = Field(description="0.0-1.0: does the answer match the reference answer's facts?")
    faithfulness: float = Field(description="0.0-1.0: is the answer supported by the evidence, with no invented facts?")
    reasoning: str = Field(description="One short sentence explaining the scores.")


def _judge(question: str, reference: str, answer: str, evidence: str) -> JudgeScore:
    llm = get_llm().with_structured_output(JudgeScore)
    prompt = (
        f"Question: {question}\n"
        f"Reference answer: {reference}\n"
        f"System's answer: {answer}\n"
        f"Evidence the system had access to: {evidence}\n\n"
        f"Score correctness (matches the reference's facts) and faithfulness "
        f"(supported by the evidence, nothing invented), each 0.0-1.0."
    )
    return llm.invoke(prompt)


def _agent_used(steps: list) -> str:
    used = [s for s in steps if s in ("retriever", "web", "data(sql)", "code")]
    return ", ".join(used) if used else "(none)"


def _routed_correctly(steps: list, expected: str) -> bool:
    agent_step_map = {"retriever": "retriever", "web": "web", "data": "data(sql)", "code": "code"}
    return agent_step_map.get(expected, expected) in steps


def evaluate() -> list[dict]:
    results = []

    for i, item in enumerate(EVAL_QUESTIONS, 1):
        print(f"[{i}/{len(EVAL_QUESTIONS)}] Running: {item['question']}")
        start = time.time()
        try:
            state = run(item["question"], use_memory=False)
        except Exception as exc:
            print(f"  FAILED: {exc}")
            results.append({
                "question": item["question"],
                "expected_agent": item["expects_agent"],
                "agent_used": "(error)",
                "routed_correctly": False,
                "answer": f"ERROR: {exc}",
                "correctness": 0.0,
                "faithfulness": 0.0,
                "judge_reasoning": "n/a — run failed",
                "latency_s": round(time.time() - start, 2),
                "revisions": None,
            })
            continue
        latency = round(time.time() - start, 2)

        evidence = "\n".join(filter(None, [
            "\n".join(state.get("documents", [])),
            state.get("web_result"),
            state.get("sql_result"),
            state.get("code_result"),
        ]))

        score = _judge(item["question"], item["reference"], state.get("answer", ""), evidence)

        results.append({
            "question": item["question"],
            "expected_agent": item["expects_agent"],
            "agent_used": _agent_used(state.get("steps", [])),
            "routed_correctly": _routed_correctly(state.get("steps", []), item["expects_agent"]),
            "answer": state.get("answer"),
            "correctness": score.correctness,
            "faithfulness": score.faithfulness,
            "judge_reasoning": score.reasoning,
            "latency_s": latency,
            "revisions": state.get("revisions", 0),
        })
        print(f"  done in {latency}s — steps: {state.get('steps', [])}")

    return results


def print_report(results: list[dict]) -> None:
    print(f"{'Question':<55} {'Route OK':<9} {'Correct':<8} {'Faithful':<9} {'Latency':<8}")
    print("-" * 95)
    for r in results:
        q = (r["question"][:52] + "...") if len(r["question"]) > 55 else r["question"]
        print(f"{q:<55} {str(r['routed_correctly']):<9} {r['correctness']:<8.2f} "
              f"{r['faithfulness']:<9.2f} {r['latency_s']:<8.2f}")

    n = len(results)
    avg_correct = sum(r["correctness"] for r in results) / n
    avg_faithful = sum(r["faithfulness"] for r in results) / n
    routing_acc = sum(r["routed_correctly"] for r in results) / n
    avg_latency = sum(r["latency_s"] for r in results) / n

    print("-" * 95)
    print(f"Averages: correctness={avg_correct:.2f}  faithfulness={avg_faithful:.2f}  "
          f"routing_accuracy={routing_acc:.2f}  latency={avg_latency:.2f}s")


if __name__ == "__main__":
    settings.validate()
    results = evaluate()
    print_report(results)

    with open("eval_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("\nFull results written to eval_results.json")
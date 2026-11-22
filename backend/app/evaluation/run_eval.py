"""Benchmark vector RAG vs graph RAG vs hybrid GraphRAG with an LLM judge.

    python -m app.evaluation.run_eval --modes vector graph hybrid
Writes eval_results/results.json and eval_results/results.md
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel

from ..llm import get_llm
from ..rag.answer import ask

QUESTIONS = Path(__file__).with_name("questions.json")


class Verdict(BaseModel):
    correct: bool
    reason: str


def judge(question: str, expected: str, answer: str) -> Verdict:
    prompt = (
        "You grade answers to company-knowledge questions.\n"
        f"Question: {question}\nReference answer: {expected}\nCandidate answer: {answer}\n\n"
        "The candidate is correct if it contains all key facts of the reference answer and does not "
        "contradict it. Extra detail is fine. Refusals or 'not enough information' are incorrect."
    )
    return get_llm().with_structured_output(Verdict).invoke(prompt)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", nargs="+", default=["vector", "graph", "hybrid"])
    args = ap.parse_args()
    questions = json.loads(QUESTIONS.read_text())

    rows, stats = [], defaultdict(lambda: defaultdict(list))
    for mode in args.modes:
        for q in questions:
            res = ask(q["question"], mode=mode)
            v = judge(q["question"], q["expected"], res["answer"])
            stats[mode]["all"].append(v.correct)
            stats[mode][q["type"]].append(v.correct)
            stats[mode]["latency"].append(res["latency_ms"])
            rows.append({"mode": mode, **q, "answer": res["answer"], "correct": v.correct, "reason": v.reason,
                         "latency_ms": res["latency_ms"]})
            print(f"[{mode:6}] Q{q['id']:>2} {'OK ' if v.correct else 'FAIL'} {q['question'][:70]}")

    def pct(xs):
        return f"{100 * sum(xs) / len(xs):.0f}%" if xs else "-"

    md = ["| Mode | Overall | Single-hop | Multi-hop | Avg latency (ms) |", "|---|---|---|---|---|"]
    for mode in args.modes:
        s = stats[mode]
        md.append(f"| {mode} | {pct(s['all'])} | {pct(s['single-hop'])} | {pct(s['multi-hop'])} | "
                  f"{sum(s['latency']) // max(len(s['latency']), 1)} |")
    out = Path("eval_results")
    out.mkdir(exist_ok=True)
    (out / "results.json").write_text(json.dumps(rows, indent=2))
    (out / "results.md").write_text("\n".join(md) + "\n")
    print("\n" + "\n".join(md))


if __name__ == "__main__":
    main()

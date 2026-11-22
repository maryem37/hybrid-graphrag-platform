import time

from ..llm import get_llm
from ..retrieval.hybrid import retrieve

SYSTEM = """You are an enterprise knowledge assistant answering questions about a company's documents.
Use ONLY the GRAPH FACTS and PASSAGES provided. For multi-hop questions, chain the facts step by step
(for example person -> manager -> department -> director) and say which link comes from where.
Cite passages as [S1], [S2]. Graph facts are hints extracted automatically: when a passage contradicts a
fact, trust the passage. If the context is not enough, say exactly what is missing instead of guessing.
Be concise."""


def build_context(retr: dict) -> str:
    parts = []
    if retr["facts"]:
        lines = [f"- {f['a_name']} ({f['a_type']}) -[{f['rel']}]-> {f['b_name']} ({f['b_type']})" for f in retr["facts"]]
        parts.append("GRAPH FACTS:\n" + "\n".join(lines))
    if retr["chunks"]:
        blocks = [f"[S{i}] ({c['source']}, p.{c['page']})\n{c['text']}" for i, c in enumerate(retr["chunks"], 1)]
        parts.append("PASSAGES:\n" + "\n\n".join(blocks))
    return "\n\n".join(parts) or "(no context retrieved)"


def ask(question: str, mode: str = "hybrid", hops: int = 2) -> dict:
    t0 = time.perf_counter()
    retr = retrieve(question, mode=mode, hops=hops)
    context = build_context(retr)
    reply = get_llm().invoke([("system", SYSTEM), ("human", f"{context}\n\nQUESTION: {question}")])
    answer_text = reply.content if isinstance(reply.content, str) else str(reply.content or "")
    return {
        "answer": answer_text,
        "mode": mode,
        "entities": retr["entities"],
        "linked": [s["name"] for s in retr["seeds"]],
        "facts": len(retr["facts"]),
        "sources": [
            {"label": f"S{i}", "source": c["source"], "page": c["page"], "snippet": c["text"][:400]}
            for i, c in enumerate(retr["chunks"], 1)
        ],
        "graph": retr["graph"],
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }

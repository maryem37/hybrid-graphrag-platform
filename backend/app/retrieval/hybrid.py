"""Hybrid retrieval: vector search + entity linking (full-text, fuzzy) + multi-hop graph traversal.

modes
  vector  baseline RAG (chunk embeddings only)
  graph   entity linking + graph facts + chunks that support those facts
  hybrid  both, fused with Reciprocal Rank Fusion (RRF)
"""
import logging
from collections import Counter, defaultdict

from pydantic import BaseModel, Field

from ..config import get_settings
from ..db import run
from ..llm import get_embeddings, get_llm
from ..utils import fuzzy_query

log = logging.getLogger("nexagraph.retrieval")
MAX_FACTS = 25


class _Entities(BaseModel):
    names: list[str] = Field(
        default_factory=list,
        description="Distinct named entities in the question: people, projects, clients, departments, "
        "technologies, products, locations, certifications. Use the names exactly as written.",
    )


def extract_entities(question: str) -> list[str]:
    try:
        res = get_llm().with_structured_output(_Entities).invoke(
            [("system", "Extract the named entities needed to answer the question."), ("human", question)]
        )
        return [n.strip() for n in res.names if n.strip()][:8]
    except Exception as exc:
        log.warning("Entity extraction failed: %s", exc)
        return []


Q_SEED = """
CALL db.index.fulltext.queryNodes('entity_names', $q, {limit: 5}) YIELD node, score
RETURN node.key AS key, node.name AS name, node.type AS type, score
"""


def find_seeds(names: list[str]) -> list[dict]:
    """Link question entities to graph nodes (typo tolerant, keeps only near-top matches)."""
    best: dict[str, dict] = {}
    for name in names:
        try:
            rows = run(Q_SEED, q=fuzzy_query(name))
        except Exception as exc:
            log.warning("Seed lookup failed for %r: %s", name, exc)
            continue
        if not rows:
            continue
        top = rows[0]["score"]
        for r in rows:
            if r["score"] >= 0.6 * top and (r["key"] not in best or r["score"] > best[r["key"]]["score"]):
                best[r["key"]] = r
    return sorted(best.values(), key=lambda r: -r["score"])[:8]


def expand(keys: list[str], hops: int, limit: int = 400) -> list[dict]:
    """All relationships within `hops` of the seeds. Hub nodes are not traversed *through*."""
    hops = max(1, min(int(hops), 3))
    query = f"""
    UNWIND $keys AS k
    MATCH (s:Entity {{key: k}})
    MATCH p = (s)-[:REL*1..{hops}]-(:Entity)
    WHERE all(x IN nodes(p)[1..-1] WHERE coalesce(x.degree, 0) <= $max_degree)
    UNWIND relationships(p) AS r
    WITH DISTINCT r
    RETURN startNode(r).key AS a_key, startNode(r).name AS a_name, startNode(r).type AS a_type,
           r.type AS rel,
           endNode(r).key AS b_key, endNode(r).name AS b_name, endNode(r).type AS b_type,
           r.sources AS sources
    LIMIT $limit
    """
    return run(query, keys=keys, max_degree=get_settings().max_hub_degree, limit=limit)


def mention_hits(keys: list[str], limit: int = 20) -> list[dict]:
    return run(
        """
        UNWIND $keys AS k
        MATCH (c:Chunk)-[:MENTIONS]->(:Entity {key: k})
        WITH c, count(*) AS hits
        RETURN c.id AS id, hits ORDER BY hits DESC LIMIT $limit
        """,
        keys=keys, limit=limit,
    )


def fetch_chunks(ids: list[str]) -> list[dict]:
    if not ids:
        return []
    return run(
        "MATCH (c:Chunk) WHERE c.id IN $ids RETURN c.id AS id, c.text AS text, c.source AS source, c.page AS page",
        ids=ids,
    )


def vector_search(question: str, k: int) -> list[dict]:
    vec = get_embeddings().embed_query(question)
    return run(
        """
        CALL db.index.vector.queryNodes('chunk_embeddings', $k, $vec) YIELD node, score
        RETURN node.id AS id, node.text AS text, node.source AS source, node.page AS page, score
        """,
        k=k, vec=vec,
    )


def rrf(*ranked: list[str], k: int = 60) -> list[str]:
    scores: dict[str, float] = defaultdict(float)
    for lst in ranked:
        for i, cid in enumerate(lst):
            scores[cid] += 1.0 / (k + i + 1)
    return sorted(scores, key=lambda cid: -scores[cid])


def retrieve(question: str, mode: str = "hybrid", hops: int = 2, top_k: int = 6) -> dict:
    entities: list[str] = []
    seeds: list[dict] = []
    facts: list[dict] = []
    graph_ids: list[str] = []
    vec_chunks: list[dict] = []

    if mode in ("graph", "hybrid"):
        entities = extract_entities(question)
        seeds = find_seeds(entities)
        if seeds:
            seed_keys = [s["key"] for s in seeds]
            facts = expand(seed_keys, hops)
            facts.sort(key=lambda f: 0 if f["a_key"] in seed_keys or f["b_key"] in seed_keys else 1)
            facts = facts[:MAX_FACTS]
            votes: Counter = Counter()
            for f in facts:
                weight = 2 if f["a_key"] in seed_keys or f["b_key"] in seed_keys else 1
                for cid in f.get("sources") or []:
                    votes[cid] += weight
            for row in mention_hits(seed_keys):
                votes[row["id"]] += row["hits"]
            graph_ids = [cid for cid, _ in votes.most_common(8)]

    if mode in ("vector", "hybrid"):
        vec_chunks = vector_search(question, top_k)

    chunk_map = {c["id"]: c for c in vec_chunks}
    for c in fetch_chunks(graph_ids):
        chunk_map.setdefault(c["id"], c)
    order = rrf([c["id"] for c in vec_chunks], graph_ids)[:top_k]
    chunks = [chunk_map[i] for i in order if i in chunk_map]

    return {
        "entities": entities,
        "seeds": seeds,
        "facts": facts,
        "chunks": chunks,
        "graph": _graph_payload(seeds, facts),
    }


def _graph_payload(seeds: list[dict], facts: list[dict]) -> dict:
    seed_keys = {s["key"] for s in seeds}
    nodes: dict[str, dict] = {s["key"]: {"id": s["key"], "name": s["name"], "type": s["type"], "seed": True} for s in seeds}
    links = []
    for f in facts:
        for side in ("a", "b"):
            key = f[f"{side}_key"]
            nodes.setdefault(key, {"id": key, "name": f[f"{side}_name"], "type": f[f"{side}_type"], "seed": key in seed_keys})
        links.append({"source": f["a_key"], "target": f["b_key"], "label": f["rel"]})
    return {"nodes": list(nodes.values()), "links": links}

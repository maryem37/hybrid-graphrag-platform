import logging

from neo4j import GraphDatabase

from .config import get_settings

log = logging.getLogger("nexagraph.db")
_driver = None


def driver():
    global _driver
    if _driver is None:
        s = get_settings()
        _driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    return _driver


def run(query: str, **params) -> list[dict]:
    with driver().session() as session:
        return [r.data() for r in session.run(query, **params)]


def ensure_schema() -> None:
    """Constraints + full-text + vector indexes (idempotent)."""
    dim = get_settings().embedding_dim
    statements = [
        "CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
        "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT entity_key IF NOT EXISTS FOR (e:Entity) REQUIRE e.key IS UNIQUE",
        "CREATE FULLTEXT INDEX entity_names IF NOT EXISTS FOR (e:Entity) ON EACH [e.name]",
        "CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS FOR (c:Chunk) ON EACH [c.text]",
        (
            "CREATE VECTOR INDEX chunk_embeddings IF NOT EXISTS FOR (c:Chunk) ON (c.embedding) "
            f"OPTIONS {{indexConfig: {{`vector.dimensions`: {dim}, `vector.similarity_function`: 'cosine'}}}}"
        ),
    ]
    for stmt in statements:
        run(stmt)
    log.info("Neo4j schema ready")

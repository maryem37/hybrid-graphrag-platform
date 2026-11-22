"""PDF -> chunks -> embeddings -> LLM entity/relation extraction -> Neo4j.

Graph schema
  (:Document)-[:HAS_CHUNK]->(:Chunk {text, page, source, embedding})
  (:Chunk)-[:MENTIONS]->(:Entity {key, name, type, degree})
  (:Entity)-[:REL {type, sources:[chunk ids]}]->(:Entity)
Every relationship keeps the chunk ids it was extracted from (provenance).
"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..config import get_settings
from ..db import ensure_schema, run
from ..llm import get_embeddings, get_llm
from ..utils import clean_rel_type, normalize_key

log = logging.getLogger("nexagraph.ingest")

ALLOWED_NODES = [
    "Person", "Organization", "Client", "Department", "Project", "Product", "Technology",
    "Role", "Location", "Certification", "Industry", "Policy", "Concept",
]
EXTRA_INSTRUCTIONS = (
    "Use the full name exactly as written as the node id (people, projects, clients). "
    "Prefer these relationship types when they fit: REPORTS_TO, MANAGES, WORKS_ON, LEADS, "
    "PROJECT_MANAGER_OF, TECHNICAL_LEAD_OF, ACCOUNT_MANAGER_OF, CLIENT_OF, BELONGS_TO_DEPARTMENT, "
    "LOCATED_IN, USES, HOLDS_CERTIFICATION, HAS_ROLE, HAS_STATUS, OWNED_BY, PART_OF."
)

WRITE_CHUNK = """
MERGE (d:Document {id: $doc_id}) SET d.name = $source
MERGE (c:Chunk {id: $chunk_id})
SET c.text = $text, c.page = $page, c.source = $source, c.embedding = $embedding
MERGE (d)-[:HAS_CHUNK]->(c)
WITH c
UNWIND $nodes AS n
  MERGE (e:Entity {key: n.key})
  ON CREATE SET e.name = n.name, e.type = n.type
  MERGE (c)-[:MENTIONS]->(e)
WITH DISTINCT c
UNWIND $rels AS r
  MATCH (a:Entity {key: r.source}), (b:Entity {key: r.target})
  MERGE (a)-[x:REL {type: r.type}]->(b)
  ON CREATE SET x.sources = [$chunk_id]
  ON MATCH SET x.sources = CASE WHEN $chunk_id IN x.sources THEN x.sources ELSE x.sources + $chunk_id END
"""

STATUS: dict = {"state": "idle", "message": "", "done": 0, "total": 0, "errors": 0}
_lock = threading.Lock()


def get_status() -> dict:
    return dict(STATUS)


def start_ingest(reset: bool = False) -> bool:
    with _lock:
        if STATUS["state"] == "running":
            return False
        STATUS.update(state="running", message="Starting", done=0, total=0, errors=0)
    threading.Thread(target=_run, args=(reset,), daemon=True).start()
    return True


def load_chunks(path: Path) -> list[Document]:
    s = get_settings()
    pages = PyPDFLoader(str(path)).load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=s.chunk_size, chunk_overlap=s.chunk_overlap)
    chunks = splitter.split_documents(pages)
    for i, c in enumerate(chunks):
        c.metadata.update(
            source=path.name, doc_id=path.stem, page=int(c.metadata.get("page", 0)) + 1,
            chunk_id=f"{path.stem}:{i}",
        )
    return chunks


def _extract(transformer: LLMGraphTransformer, chunk: Document):
    try:
        return transformer.convert_to_graph_documents([chunk])[0]
    except Exception as exc:  # one bad chunk must not stop the run
        log.warning("Extraction failed for %s: %s", chunk.metadata["chunk_id"], exc)
        return None


def _write(chunk: Document, embedding: list[float], gdoc) -> None:
    nodes: dict[str, dict] = {}
    rels: list[dict] = []
    if gdoc is not None:
        for n in gdoc.nodes:
            name = str(n.id).strip()
            if len(name) >= 2:
                nodes[normalize_key(name)] = {"key": normalize_key(name), "name": name, "type": n.type}
        for r in gdoc.relationships:
            src, tgt = normalize_key(str(r.source.id)), normalize_key(str(r.target.id))
            if not src or not tgt or src == tgt:
                continue
            for key, node in ((src, r.source), (tgt, r.target)):
                nodes.setdefault(key, {"key": key, "name": str(node.id).strip(), "type": node.type})
            rels.append({"source": src, "target": tgt, "type": clean_rel_type(r.type)})
    m = chunk.metadata
    run(
        WRITE_CHUNK, doc_id=m["doc_id"], source=m["source"], chunk_id=m["chunk_id"], text=chunk.page_content,
        page=m["page"], embedding=embedding, nodes=list(nodes.values()), rels=rels,
    )


def _run(reset: bool) -> None:
    s = get_settings()
    try:
        ensure_schema()
        if reset:
            STATUS["message"] = "Clearing existing graph"
            run("MATCH (n) DETACH DELETE n")
        files = sorted(Path(s.data_dir).glob("*.pdf"))
        if not files:
            raise RuntimeError(f"No PDF files found in {Path(s.data_dir).resolve()}")

        STATUS["message"] = "Reading and chunking PDFs"
        chunks = [c for f in files for c in load_chunks(f)]
        STATUS["total"] = len(chunks)

        STATUS["message"] = "Computing embeddings"
        emb = get_embeddings()
        vectors: list[list[float]] = []
        for i in range(0, len(chunks), 64):
            vectors += emb.embed_documents([c.page_content for c in chunks[i : i + 64]])

        STATUS["message"] = "Extracting entities and relationships"
        transformer = LLMGraphTransformer(
            llm=get_llm(), allowed_nodes=ALLOWED_NODES, strict_mode=True,
            node_properties=False, relationship_properties=False,
            additional_instructions=EXTRA_INSTRUCTIONS,
        )
        with ThreadPoolExecutor(max_workers=s.ingest_workers) as pool:
            for chunk, vec, gdoc in zip(chunks, vectors, pool.map(lambda c: _extract(transformer, c), chunks)):
                if gdoc is None:
                    STATUS["errors"] += 1
                _write(chunk, vec, gdoc)
                STATUS["done"] += 1

        run("MATCH (e:Entity) SET e.degree = size([(e)-[:REL]-() | 1])")
        STATUS.update(state="done", message=f"Ingested {len(files)} documents / {len(chunks)} chunks")
    except Exception as exc:
        log.exception("Ingestion failed")
        STATUS.update(state="error", message=str(exc))

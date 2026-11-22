import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import get_settings
from .db import ensure_schema, run
from .ingestion import pipeline
from .rag.answer import ask

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nexagraph")


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        ensure_schema()
    except Exception as exc:  # Neo4j may still be starting; schema is also ensured at ingestion time
        log.warning("Schema setup skipped: %s", exc)
    yield


app = FastAPI(title="NexaGraph - Hybrid GraphRAG API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=get_settings().cors_origins.split(","), allow_methods=["*"], allow_headers=["*"]
)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    mode: Literal["vector", "graph", "hybrid"] = "hybrid"
    hops: int = Field(default=2, ge=1, le=3)


class IngestRequest(BaseModel):
    reset: bool = False


def _data_dir() -> Path:
    p = Path(get_settings().data_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


@app.get("/api/health")
def health():
    try:
        run("RETURN 1 AS ok")
        return {"status": "ok", "neo4j": True}
    except Exception as exc:
        return {"status": "degraded", "neo4j": False, "detail": str(exc)}


@app.get("/api/stats")
def stats():
    counts = run(
        "RETURN COUNT { (:Document) } AS documents, COUNT { (:Chunk) } AS chunks, "
        "COUNT { (:Entity) } AS entities, COUNT { ()-[:REL]->() } AS relationships"
    )[0]
    types = run("MATCH (e:Entity) RETURN coalesce(e.type, 'Unknown') AS type, count(*) AS n ORDER BY n DESC")
    return {**counts, "entity_types": types, "pdfs_in_data_dir": sorted(f.name for f in _data_dir().glob("*.pdf"))}


@app.post("/api/upload")
def upload(files: list[UploadFile] = File(...)):
    saved = []
    for f in files:
        name = Path(f.filename or "").name
        if not name.lower().endswith(".pdf"):
            raise HTTPException(400, f"Only PDF files are accepted: {name}")
        (_data_dir() / name).write_bytes(f.file.read())
        saved.append(name)
    return {"saved": saved}


@app.post("/api/ingest")
def ingest(req: IngestRequest):
    if not pipeline.start_ingest(req.reset):
        raise HTTPException(409, "An ingestion is already running")
    return pipeline.get_status()


@app.get("/api/ingest/status")
def ingest_status():
    return pipeline.get_status()


@app.post("/api/ask")
def ask_endpoint(req: AskRequest):
    try:
        return ask(req.question, mode=req.mode, hops=req.hops)
    except Exception as exc:
        log.exception("ask failed")
        raise HTTPException(500, f"{type(exc).__name__}: {exc}")


@app.get("/api/graph")
def graph(limit: int = 120):
    """Overview: the most connected entities and the links among them."""
    limit = max(10, min(limit, 400))
    nodes = run(
        "MATCH (e:Entity) RETURN e.key AS id, e.name AS name, e.type AS type, coalesce(e.degree, 0) AS degree "
        "ORDER BY degree DESC LIMIT $n", n=limit,
    )
    keys = [n["id"] for n in nodes]
    links = run(
        "MATCH (a:Entity)-[r:REL]->(b:Entity) WHERE a.key IN $keys AND b.key IN $keys "
        "RETURN a.key AS source, b.key AS target, r.type AS label", keys=keys,
    )
    return {"nodes": nodes, "links": links}

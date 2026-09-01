"""Minimal FastAPI endpoint exposing the maintenance assistant.

Run:  uvicorn app.api:app --reload
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.generate.answer import answer

app = FastAPI(title="RAG Automotive Maintenance Assistant")

# The UI is served same-origin from /, so CORS isn't needed for that. It's here
# so the frontend can also be run from a separate dev server (e.g. a Vite/Live
# Server on another port) against this API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Query(BaseModel):
    question: str
    make: str | None = None
    model: str | None = None
    year: int | None = None
    reasoning: bool = False


@app.post("/ask")
def ask(q: Query):
    return answer(q.question, q.make, q.model, q.year, q.reasoning)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/vehicles")
def vehicles():
    """Makes/models/variants that are actually indexed (grounded answers only
    exist for these). Lets the UI scope its selector to answerable vehicles."""
    import sqlite3
    from app.config import SETTINGS

    out: dict[str, dict[str, list[dict]]] = {}
    try:
        con = sqlite3.connect(f"{SETTINGS.stores_dir}/chunks.sqlite")
        rows = con.execute(
            "SELECT DISTINCT make, model, variant FROM chunks "
            "WHERE make!='' ORDER BY make, model, variant"
        ).fetchall()
        con.close()
    except sqlite3.OperationalError:
        return {"vehicles": {}, "note": "no index built yet"}

    from app.ingest.manifest import parse_variant_years
    for make, model, variant in rows:
        ys, ye = parse_variant_years(variant or "")
        out.setdefault(make, {}).setdefault(model, []).append(
            {"variant": variant, "year_start": ys, "year_end": ye}
        )
    return {"vehicles": out}


# Mounted last so it never shadows the routes above: the GarageMind UI mockup
# (visual only -- it does not call /ask, see rag-automotive/web/app.js).
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

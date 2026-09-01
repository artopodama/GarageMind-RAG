"""Chunk, embed, and index the crawled manuals corpus.

Reads ``data/manuals/<brand>/<model>/<variant>/**/*.md`` **in place** (no copy of
the 18 GB tree), injecting the derived scope metadata — ``manual_id``, ``make``,
``brand``, ``model``, ``variant``, ``year_start/end`` (from ``manifest.py``) — into
every chunk so ``hybrid.py``'s ``where={"manual_id": ...}`` filter actually works.

Builds two indexes:
  * **Chroma** (semantic) — incremental ``upsert`` per brand.
  * **BM25** (lexical) — rebuilt from a persistent chunk store (SQLite).

Designed to survive this machine's limits (16 GB RAM, ~23 GB free disk, CPU/MPS
embedding over ~280k potential chunks): it runs **brand-by-brand and is
resumable** (a completed brand is skipped on re-run), checks free disk before
each brand and **stops gracefully** rather than filling the disk, and processes
one brand's chunks at a time to bound peak RAM. Prove-then-expand: index one
brand, verify the whole pipeline, then let the rest run.

Usage:
  python -m app.ingest.build_index --brands toyota            # one brand
  python -m app.ingest.build_index --brands toyota,honda,vw   # several
  python -m app.ingest.build_index --all                      # everything
  python -m app.ingest.build_index --brands toyota --limit-files 40  # smoke test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import pickle
import shutil
import sqlite3

import chromadb
import frontmatter
from rank_bm25 import BM25Okapi

from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from app.config import SETTINGS
from app.ingest.manifest import meta_for_md_path, build_manifest

MANUALS = pathlib.Path(SETTINGS.manuals_dir)
STORES = pathlib.Path(SETTINGS.stores_dir)
CHUNK_DB = STORES / "chunks.sqlite"          # persistent chunk store (BM25 source)
STATE = STORES / "index_state.json"          # {"brands_done": [...]}
CHROMA_DIR = STORES / "chroma"

_CHUNK_DDL = """
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id   TEXT PRIMARY KEY,
    text       TEXT NOT NULL,
    manual_id  TEXT, make TEXT, brand TEXT, model TEXT, variant TEXT,
    year_start INTEGER, year_end INTEGER,
    section    TEXT, source_url TEXT
);
CREATE INDEX IF NOT EXISTS idx_chunk_manual ON chunks(manual_id);
CREATE INDEX IF NOT EXISTS idx_chunk_brand ON chunks(brand);
"""


def _free_gb(path: pathlib.Path) -> float:
    return shutil.disk_usage(path).free / 1024**3


def _load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"brands_done": []}


def _save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2))


def load_brand_docs(brand: str, limit_files: int | None = None) -> list[Document]:
    """One Document per .md under a brand, with derived scope metadata injected."""
    docs = []
    brand_dir = MANUALS / brand
    if not brand_dir.exists():
        return docs
    for p in sorted(brand_dir.rglob("*.md")):
        try:
            post = frontmatter.load(p)
        except Exception:
            continue
        if not post.content.strip():
            continue
        m = meta_for_md_path(p, MANUALS)
        fm = post.metadata
        meta = {
            "manual_id": m.manual_id, "make": m.make, "brand": m.brand,
            "model": m.model, "variant": m.variant,
            "year_start": m.year_start if m.year_start is not None else 0,
            "year_end": m.year_end if m.year_end is not None else 0,
            "section": str(fm.get("section") or ""),
            "subsection": str(fm.get("subsection") or ""),
            "title": str(fm.get("title") or ""),
            "source_url": str(fm.get("source_url") or ""),
            "rel_path": str(p.relative_to(MANUALS)),
        }
        docs.append(Document(text=post.content, metadata=meta))
        if limit_files and len(docs) >= limit_files:
            break
    return docs


def chunk(docs: list[Document]):
    """Structure-aware (Markdown headings/tables) then size-bounded so chunks fit
    the embedder's window and make focused, citable passages."""
    md_nodes = MarkdownNodeParser().get_nodes_from_documents(docs)
    splitter = SentenceSplitter(
        chunk_size=SETTINGS.chunk_tokens, chunk_overlap=SETTINGS.chunk_overlap
    )
    return splitter.get_nodes_from_documents(md_nodes)


def _chunk_id(node) -> str:
    # Deterministic id = source file + content hash. Stable across runs (unlike
    # llama-index's random node_id), so re-running a brand upserts over the same
    # ids instead of creating duplicates — the property that makes the big
    # "everything" build safely resumable/restartable.
    md = node.metadata
    h = hashlib.md5(node.get_content().encode("utf-8")).hexdigest()[:10]
    return f"{md.get('rel_path','?')}::{h}"


def _open_chunk_db() -> sqlite3.Connection:
    STORES.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(CHUNK_DB)
    con.executescript(_CHUNK_DDL)
    return con


def index_brand(brand: str, embed: HuggingFaceEmbedding,
                col, con: sqlite3.Connection, limit_files: int | None = None) -> int:
    docs = load_brand_docs(brand, limit_files=limit_files)
    if not docs:
        print(f"  [{brand}] no docs found, skipping")
        return 0
    nodes = chunk(docs)
    texts = [n.get_content() for n in nodes]
    ids = [_chunk_id(n) for n in nodes]
    metas = [dict(n.metadata) for n in nodes]

    # Batch-embed (MPS/GPU) — far faster than the shipped per-chunk loop.
    embs = embed.get_text_embedding_batch(texts, show_progress=True)

    # Chroma caps a single upsert (~5461 rows); split into sub-batches so a
    # large brand doesn't blow the limit. Write the chunk store in lockstep.
    UPSERT_MAX = 4000
    for s in range(0, len(ids), UPSERT_MAX):
        e = s + UPSERT_MAX
        col.upsert(ids=ids[s:e], documents=texts[s:e],
                   metadatas=metas[s:e], embeddings=embs[s:e])
        con.executemany(
            "INSERT OR REPLACE INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [
                (ids[i], texts[i], m.get("manual_id"), m.get("make"), m.get("brand"),
                 m.get("model"), m.get("variant"), m.get("year_start"),
                 m.get("year_end"), m.get("section"), m.get("source_url"))
                for i, m in enumerate(metas[s:e], start=s)
            ],
        )
        con.commit()
    print(f"  [{brand}] {len(docs)} docs -> {len(nodes)} chunks indexed")
    return len(nodes)


def rebuild_bm25() -> int:
    """Rebuild bm25.pkl from the whole persistent chunk store. This is the one
    full-corpus-in-RAM step; cheap for a few brands, heavy for everything."""
    con = _open_chunk_db()
    rows = con.execute(
        "SELECT chunk_id, text, manual_id, make, model, variant, section "
        "FROM chunks"
    ).fetchall()
    con.close()
    ids = [r[0] for r in rows]
    texts = [r[1] for r in rows]
    metas = [
        {"manual_id": r[2], "make": r[3], "model": r[4], "variant": r[5],
         "section": r[6]}
        for r in rows
    ]
    bm25 = BM25Okapi([t.split() for t in texts])
    with open(STORES / "bm25.pkl", "wb") as f:
        pickle.dump({"bm25": bm25, "texts": texts, "ids": ids, "metas": metas}, f)
    return len(ids)


def build(brands: list[str], limit_files: int | None = None,
          min_free_gb: float = 3.0, rebuild_lexical: bool = True) -> None:
    if not pathlib.Path(SETTINGS.manifest_db).exists():
        print("Manifest missing — building it first...")
        build_manifest()

    STORES.mkdir(parents=True, exist_ok=True)
    embed = HuggingFaceEmbedding(
        model_name=SETTINGS.embed_model,
        device=SETTINGS.embed_device,
        embed_batch_size=SETTINGS.embed_batch_size,
    )
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    col = client.get_or_create_collection("manuals")
    con = _open_chunk_db()
    state = _load_state()

    total, stopped = 0, False
    for brand in brands:
        if brand in state["brands_done"]:
            print(f"[{brand}] already indexed, skipping (resumable)")
            continue
        free = _free_gb(STORES)
        if free < min_free_gb:
            print(f"STOP: only {free:.1f} GB free (< {min_free_gb} GB). "
                  f"Stopping before '{brand}' to avoid filling the disk.")
            stopped = True
            break
        print(f"[{brand}] indexing (free disk {free:.1f} GB)...")
        n = index_brand(brand, embed, col, con, limit_files=limit_files)
        total += n
        state["brands_done"].append(brand)
        _save_state(state)

    con.close()
    if rebuild_lexical:
        print("Rebuilding BM25 from chunk store...")
        n_bm = rebuild_bm25()
        print(f"BM25 rebuilt over {n_bm} chunks.")

    done = ", ".join(state["brands_done"]) or "(none)"
    print(f"\nDone. Chunks added this run: {total}. Brands indexed: {done}.")
    print(f"Free disk: {_free_gb(STORES):.1f} GB." + (" [STOPPED EARLY]" if stopped else ""))


def _all_brands() -> list[str]:
    return sorted(p.name for p in MANUALS.iterdir() if p.is_dir())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--brands", help="comma-separated brand dir names, e.g. toyota,honda")
    g.add_argument("--all", action="store_true", help="index every brand")
    ap.add_argument("--limit-files", type=int, default=None,
                    help="cap .md files per brand (smoke test)")
    ap.add_argument("--min-free-gb", type=float, default=3.0)
    ap.add_argument("--no-bm25", action="store_true",
                    help="skip BM25 rebuild (do it once at the end of a big run)")
    args = ap.parse_args()

    brands = _all_brands() if args.all else [b.strip() for b in args.brands.split(",")]
    build(brands, limit_files=args.limit_files, min_free_gb=args.min_free_gb,
          rebuild_lexical=not args.no_bm25)

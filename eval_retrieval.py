#!/usr/bin/env python
"""
GarageMind retrieval benchmark.

Compares:
  1) Dense only
  2) BM25 only
  3) Hybrid RRF
  4) Hybrid + rerank

Metrics:
  - Recall@K
  - MRR
  - nDCG@K (binary relevance)
  - latency in milliseconds (median per query; summary mean + p95)

Run from the rag-automotive repository root, for example:

    python eval_retrieval.py --eval data/eval/retrieval_eval.jsonl --k 5 --repeat 3 --out-dir outputs/retrieval_eval

JSONL format (one object per line), e.g.:

{"id":"q1","query":"What model years does this Corolla compatibility seed cover?","make":"Toyota","model":"Corolla","year":2020,"relevant_chunk_prefixes":["toyota/corolla/4-door/2018-2026/model-overview.md::"]}

Ground-truth options (use at least one):
  - relevant_chunk_ids: exact relevant chunk IDs (preferred)
  - relevant_chunk_prefixes: relevant chunk-id prefixes
  - relevant_manual_ids: all chunks in these manuals count as relevant

Notes:
  * '/' and '\\' are treated equivalently in chunk IDs.
  * Latency measures retrieval/ranking only, not Qwen/Ollama generation.
  * One warm-up pass is performed before timing.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path.cwd()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.config import SETTINGS
from app.retrieval.metadata import resolve_manual
from app.retrieval.hybrid import _dense, _bm25, retrieve
from app.retrieval.rerank import rerank

METHODS = ("dense_only", "bm25_only", "hybrid_rrf", "hybrid_rerank")
DISPLAY_NAMES = {
    "dense_only": "Dense only",
    "bm25_only": "BM25 only",
    "hybrid_rrf": "Hybrid RRF",
    "hybrid_rerank": "Hybrid + rerank",
}


def norm_id(value: str) -> str:
    return value.replace("\\", "/").strip().lower()


def load_eval(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            if not item.get("query"):
                raise ValueError(f"{path}:{line_no}: missing 'query'")
            if not any(item.get(k) for k in (
                "relevant_chunk_ids",
                "relevant_chunk_prefixes",
                "relevant_manual_ids",
            )):
                raise ValueError(
                    f"{path}:{line_no}: add relevant_chunk_ids, "
                    "relevant_chunk_prefixes, or relevant_manual_ids"
                )
            item.setdefault("id", f"q{line_no}")
            rows.append(item)
    if not rows:
        raise ValueError(f"No evaluation queries found in {path}")
    return rows


def open_chunks_db() -> sqlite3.Connection:
    db = Path(SETTINGS.stores_dir) / "chunks.sqlite"
    if not db.exists():
        raise FileNotFoundError(f"Chunk database not found: {db}")
    return sqlite3.connect(str(db))


def expand_relevant_ids(item: dict[str, Any], con: sqlite3.Connection) -> set[str]:
    relevant = {norm_id(x) for x in item.get("relevant_chunk_ids", [])}

    prefixes = [norm_id(x) for x in item.get("relevant_chunk_prefixes", [])]
    if prefixes:
        for (chunk_id,) in con.execute("SELECT chunk_id FROM chunks"):
            cid = norm_id(chunk_id)
            if any(cid.startswith(prefix) for prefix in prefixes):
                relevant.add(cid)

    manual_ids = item.get("relevant_manual_ids", [])
    if manual_ids:
        placeholders = ",".join("?" for _ in manual_ids)
        rows = con.execute(
            f"SELECT chunk_id FROM chunks WHERE manual_id IN ({placeholders})",
            list(manual_ids),
        ).fetchall()
        relevant.update(norm_id(r[0]) for r in rows)

    if not relevant:
        raise ValueError(
            f"Query {item.get('id')} has no matching relevant chunks in chunks.sqlite"
        )
    return relevant


def get_manual_id(item: dict[str, Any]) -> str | None:
    if item.get("manual_id"):
        return item["manual_id"]

    make = item.get("make")
    model = item.get("model")
    year = item.get("year")
    if make and model and year is not None:
        return resolve_manual(make, model, int(year))
    return None


def extract_chunk_ids(results: Any) -> list[str]:
    out = []
    for row in results or []:
        if isinstance(row, (tuple, list)) and row:
            out.append(str(row[0]))
        elif isinstance(row, dict):
            cid = row.get("chunk_id") or row.get("id")
            if cid is not None:
                out.append(str(cid))
        else:
            raise TypeError(f"Unsupported retrieval result row: {type(row)!r} {row!r}")
    return out


def run_dense(query: str, manual_id: str | None):
    return _dense(query, manual_id, SETTINGS.top_k_dense)


def run_bm25(query: str, manual_id: str | None):
    return _bm25(query, manual_id, SETTINGS.top_k_bm25)


def run_hybrid_rrf(query: str, manual_id: str | None):
    return retrieve(query, manual_id)


def run_hybrid_rerank(query: str, manual_id: str | None):
    candidates = retrieve(query, manual_id)
    passages, _ = rerank(query, candidates)
    return passages


RUNNERS: dict[str, Callable[[str, str | None], Any]] = {
    "dense_only": run_dense,
    "bm25_only": run_bm25,
    "hybrid_rrf": run_hybrid_rrf,
    "hybrid_rerank": run_hybrid_rerank,
}


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    top = {norm_id(x) for x in ranked[:k]}
    return len(top & relevant) / len(relevant)


def reciprocal_rank(ranked: list[str], relevant: set[str]) -> float:
    for rank, cid in enumerate(ranked, 1):
        if norm_id(cid) in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    dcg = 0.0
    for rank, cid in enumerate(ranked[:k], 1):
        if norm_id(cid) in relevant:
            dcg += 1.0 / math.log2(rank + 1)

    ideal_hits = min(len(relevant), k)
    if ideal_hits == 0:
        return 0.0
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg


def timed_run(runner, query: str, manual_id: str | None, repeat: int):
    latencies = []
    last_ids = []

    for _ in range(repeat):
        t0 = time.perf_counter()
        results = runner(query, manual_id)
        latencies.append((time.perf_counter() - t0) * 1000.0)
        last_ids = extract_chunk_ids(results)

    return last_ids, statistics.median(latencies)


def percentile(values: list[float], q: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    pos = (len(values) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return values[lo]
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


def warmup(item: dict[str, Any]) -> None:
    query = item["query"]
    manual_id = get_manual_id(item)
    print("Warm-up...")
    for method in METHODS:
        RUNNERS[method](query, manual_id)
        print(f"  {DISPLAY_NAMES[method]}: ok")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", required=True)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--out-dir", default="outputs/retrieval_eval")
    args = ap.parse_args()

    if args.k < 1:
        raise SystemExit("--k must be >= 1")
    if args.repeat < 1:
        raise SystemExit("--repeat must be >= 1")

    items = load_eval(Path(args.eval))
    out_dir = Path(args.out_dir)

    with open_chunks_db() as con:
        relevance = {
            item["id"]: expand_relevant_ids(item, con)
            for item in items
        }

    warmup(items[0])

    per_query_rows = []

    for idx, item in enumerate(items, 1):
        qid = item["id"]
        query = item["query"]
        manual_id = get_manual_id(item)
        relevant = relevance[qid]

        print(
            f"[{idx}/{len(items)}] {qid} "
            f"(scope={manual_id or 'UNSCOPED'}, relevant={len(relevant)})"
        )

        for method in METHODS:
            ranked, latency_ms = timed_run(
                RUNNERS[method], query, manual_id, args.repeat
            )
            per_query_rows.append({
                "query_id": qid,
                "method": DISPLAY_NAMES[method],
                f"recall@{args.k}": recall_at_k(ranked, relevant, args.k),
                "mrr": reciprocal_rank(ranked, relevant),
                f"ndcg@{args.k}": ndcg_at_k(ranked, relevant, args.k),
                "latency_ms": latency_ms,
                "manual_id": manual_id or "",
                "relevant_count": len(relevant),
                "returned_count": len(ranked),
                "top_ids": " | ".join(ranked[:args.k]),
            })

    summary_rows = []
    for method in METHODS:
        name = DISPLAY_NAMES[method]
        rows = [r for r in per_query_rows if r["method"] == name]
        latencies = [float(r["latency_ms"]) for r in rows]

        summary_rows.append({
            "method": name,
            "queries": len(rows),
            f"recall@{args.k}": statistics.mean(
                float(r[f"recall@{args.k}"]) for r in rows
            ),
            "mrr": statistics.mean(float(r["mrr"]) for r in rows),
            f"ndcg@{args.k}": statistics.mean(
                float(r[f"ndcg@{args.k}"]) for r in rows
            ),
            "mean_latency_ms": statistics.mean(latencies),
            "p95_latency_ms": percentile(latencies, 0.95),
        })

    per_query_path = out_dir / "per_query.csv"
    summary_path = out_dir / "summary.csv"

    write_csv(
        per_query_path,
        per_query_rows,
        [
            "query_id", "method", f"recall@{args.k}", "mrr",
            f"ndcg@{args.k}", "latency_ms", "manual_id",
            "relevant_count", "returned_count", "top_ids",
        ],
    )

    write_csv(
        summary_path,
        summary_rows,
        [
            "method", "queries", f"recall@{args.k}", "mrr",
            f"ndcg@{args.k}", "mean_latency_ms", "p95_latency_ms",
        ],
    )

    print("\n=== SUMMARY ===")
    header = (
        f"{'Method':<20}"
        f"{'Recall@'+str(args.k):>12}"
        f"{'MRR':>10}"
        f"{'nDCG@'+str(args.k):>12}"
        f"{'Latency ms':>14}"
        f"{'p95 ms':>12}"
    )
    print(header)
    print("-" * len(header))

    for row in summary_rows:
        print(
            f"{row['method']:<20}"
            f"{row[f'recall@{args.k}']:>12.4f}"
            f"{row['mrr']:>10.4f}"
            f"{row[f'ndcg@{args.k}']:>12.4f}"
            f"{row['mean_latency_ms']:>14.2f}"
            f"{row['p95_latency_ms']:>12.2f}"
        )

    print(f"\nPer-query results: {per_query_path}")
    print(f"Summary results:   {summary_path}")


if __name__ == "__main__":
    main()

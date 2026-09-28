#!/usr/bin/env python
"""
Build a 30-query gold retrieval evaluation set from the CURRENT GarageMind
chunks.sqlite.

The generated benchmark deliberately targets the unique "compatibility seed"
coverage chunks, because the seed corpus contains many duplicated safety-note
chunks. Using unique coverage chunks gives Recall@5 / MRR / nDCG@5 a meaningful
chance to distinguish Dense, BM25, Hybrid RRF and Hybrid+Rerank.

Creates:
    eval/retrieval_eval_30.jsonl

Structure:
    10 lexical/easy queries
    10 semantic/paraphrased queries
    10 harder/contrastive queries

IMPORTANT:
- Queries are intentionally UNSCOPED: the JSONL does NOT contain make/model/year
  metadata fields. The vehicle identity is written inside the query text.
  Therefore the benchmark evaluates retrieval/ranking over the corpus rather
  than the metadata resolver.
- Each query has one exact relevant_chunk_id from the real current index.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

from app.config import SETTINGS


def clean_model(model: str) -> str:
    return model.replace("-", " ").strip()


def clean_variant(variant: str) -> str:
    return variant.replace("-", " ").strip()


def infer_years(chunk_id: str, text: str, ys, ye):
    """Prefer stored metadata; otherwise infer a YYYY-YYYY range from path/text."""
    try:
        ys_i = int(ys)
        ye_i = int(ye)
        if ys_i > 0 and ye_i > 0:
            return ys_i, ye_i
    except (TypeError, ValueError):
        pass

    hay = f"{chunk_id}\n{text}"
    m = re.search(r"((?:19|20)\d{2})[-–_]((?:19|20)\d{2})", hay)
    if m:
        return int(m.group(1)), int(m.group(2))

    years = [int(x) for x in re.findall(r"(?:19|20)\d{2}", hay)]
    if years:
        return min(years), max(years)

    return None, None


def coverage_candidate(row):
    text = row["text"] or ""
    lower = text.lower()

    # The generated GarageMind seed intro chunks contain these signals.
    return (
        "garagemind compatibility seed" in lower
        and "covering" in lower
        and "year range" in lower
    )


def choose_diverse(candidates, n=30):
    """
    Prefer diversity across brands and models rather than simply taking the
    first 30 rows alphabetically.
    """
    by_brand = defaultdict(list)
    for c in candidates:
        by_brand[c["brand"]].append(c)

    for brand in by_brand:
        by_brand[brand].sort(
            key=lambda x: (x["model"], x["year_start"] or 0, x["chunk_id"])
        )

    selected = []
    used_models = set()

    # Pass 1: one generation per unique brand/model.
    changed = True
    while len(selected) < n and changed:
        changed = False
        for brand in sorted(by_brand):
            for c in by_brand[brand]:
                key = (c["brand"], c["model"])
                if key not in used_models:
                    selected.append(c)
                    used_models.add(key)
                    changed = True
                    break
            if len(selected) >= n:
                break

    # Pass 2: additional generations if fewer than 30 unique models exist.
    if len(selected) < n:
        selected_ids = {c["chunk_id"] for c in selected}
        for c in candidates:
            if c["chunk_id"] not in selected_ids:
                selected.append(c)
                selected_ids.add(c["chunk_id"])
                if len(selected) >= n:
                    break

    return selected[:n]


def lexical_query(c):
    make = c["make"]
    model = clean_model(c["model"])
    variant = clean_variant(c["variant"])
    ys, ye = c["year_start"], c["year_end"]
    return (
        f"What year range does the GarageMind compatibility seed for the "
        f"{make} {model} {variant} cover: {ys}-{ye}?"
    )


def semantic_query(c):
    make = c["make"]
    model = clean_model(c["model"])
    variant = clean_variant(c["variant"])
    ys, ye = c["year_start"], c["year_end"]
    mid = (ys + ye) // 2
    return (
        f"In the repository, which model-year generation is represented by the "
        f"{make} {model} {variant} entry that includes model year {mid}?"
    )


def hard_query(c):
    make = c["make"]
    model = clean_model(c["model"])
    variant = clean_variant(c["variant"])
    ys, ye = c["year_start"], c["year_end"]
    return (
        f"For {make} {model} {variant}, identify the generation window represented "
        f"by the seed file ({ys}-{ye}). I only need the coverage period, not tyre "
        f"pressure, torque, fluids, service intervals, or other maintenance values."
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out",
        default="eval/retrieval_eval_30.jsonl",
        help="Output JSONL path",
    )
    ap.add_argument(
        "--count",
        type=int,
        default=30,
        help="Number of queries; 30 is recommended for the thesis pilot",
    )
    args = ap.parse_args()

    db = Path(SETTINGS.stores_dir) / "chunks.sqlite"
    if not db.exists():
        raise SystemExit(f"chunks.sqlite not found: {db}")

    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT chunk_id, text, manual_id, make, brand, model, variant,
               year_start, year_end, section, source_url
        FROM chunks
        ORDER BY brand, model, year_start, chunk_id
        """
    ).fetchall()
    con.close()

    candidates = []
    for row in rows:
        if not coverage_candidate(row):
            continue

        ys, ye = infer_years(
            row["chunk_id"], row["text"], row["year_start"], row["year_end"]
        )
        if ys is None or ye is None:
            continue

        candidates.append({
            "chunk_id": row["chunk_id"],
            "manual_id": row["manual_id"],
            "make": row["make"],
            "brand": row["brand"],
            "model": row["model"],
            "variant": row["variant"],
            "year_start": ys,
            "year_end": ye,
        })

    if len(candidates) < args.count:
        raise SystemExit(
            f"Only {len(candidates)} usable coverage chunks found; "
            f"cannot build {args.count} unique queries."
        )

    selected = choose_diverse(candidates, args.count)

    # For the requested 30-query benchmark:
    # 1-10 lexical, 11-20 semantic, 21-30 harder/contrastive.
    third = args.count // 3
    remainder = args.count - (third * 3)
    sizes = [third, third, third + remainder]

    records = []
    cursor = 0

    specs = [
        ("lexical_easy", lexical_query, sizes[0]),
        ("semantic_paraphrase", semantic_query, sizes[1]),
        ("hard_contrastive", hard_query, sizes[2]),
    ]

    for category, qfun, size in specs:
        for c in selected[cursor:cursor + size]:
            records.append({
                "id": f"{category}-{len(records)+1:02d}",
                "category": category,
                "query": qfun(c),
                "relevant_chunk_ids": [c["chunk_id"]],
            })
        cursor += size

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Created {len(records)} queries: {out}")
    print()
    counts = defaultdict(int)
    for r in records:
        counts[r["category"]] += 1
    for k, v in counts.items():
        print(f"  {k}: {v}")

    print("\nSelected ground-truth chunks:")
    for r in records:
        print(f"  {r['id']}: {r['relevant_chunk_ids'][0]}")

    print(
        "\nRun benchmark with:\n"
        f"python .\\eval_retrieval_fixed.py --eval .\\{str(out).replace('/', chr(92))} "
        "--k 5 --repeat 3 --out-dir .\\outputs\\retrieval_eval_30"
    )


if __name__ == "__main__":
    main()

"""Fill in gold_chunks for the IR eval, independently of the retriever.

Each in-scope question carries a ``gold_contains`` marker — a short, distinctive
string from the passage that actually answers it. This scans the *scoped*
manual's chunks and marks those whose text contains the marker as gold. Matching
is whitespace-insensitive on both sides, because the HTML->Markdown extraction
sprinkles spaces inside words ("420 kP a", "vehi c le"); collapsing whitespace
makes the match robust to that noise.

Because gold is found by content match (not by running the retriever), the
Recall@k/MRR/NDCG numbers in run_ir.py measure the retriever against an
independent ground truth.

Run:  python -m eval.derive_gold   # rewrites questions.jsonl with gold_chunks
"""
import json
import re
import sqlite3

from app.config import SETTINGS
from app.retrieval.metadata import resolve_manual

CHUNK_DB = f"{SETTINGS.stores_dir}/chunks.sqlite"


def _despace(s: str) -> str:
    return re.sub(r"\s+", "", s).lower()


def derive(path: str = "eval/questions.jsonl") -> None:
    con = sqlite3.connect(CHUNK_DB)
    items = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]

    for item in items:
        if item.get("out_of_scope"):
            item["gold_chunks"] = []
            continue
        marker = item.get("gold_contains")
        if not marker:
            continue
        manual_id = resolve_manual(item.get("make"), item.get("model"),
                                   item.get("year"))
        rows = con.execute(
            "SELECT chunk_id, text FROM chunks WHERE manual_id=?", (manual_id,)
        ).fetchall()
        needle = _despace(marker)
        gold = [cid for cid, txt in rows if needle in _despace(txt)]
        item["gold_chunks"] = gold
        flag = "OK " if gold else "!! "
        print(f"{flag}{item['make']} {item['model']} {item.get('year')} | "
              f"'{marker}' -> {len(gold)} gold chunk(s)  [{manual_id}]")

    con.close()
    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item) + "\n")
    n_missing = sum(1 for i in items
                    if not i.get("out_of_scope") and not i.get("gold_chunks"))
    print(f"\nWrote {len(items)} items. In-scope items with no gold match: {n_missing}")


if __name__ == "__main__":
    derive()

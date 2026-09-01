"""Phase 4: classical retrieval metrics against gold passages.

Computes Recall@k, MRR, and NDCG@k using the `gold_chunks` field of the
test set, isolating the retriever from the generator.
Run:  python -m eval.run_ir
"""
import json
import math

from app.retrieval.metadata import resolve_manual
from app.retrieval.hybrid import retrieve
from app.retrieval.rerank import rerank
from app.config import SETTINGS


def dcg(rels: list[int]) -> float:
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def ndcg_at_k(retrieved_ids, gold, k):
    rels = [1 if cid in gold else 0 for cid in retrieved_ids[:k]]
    ideal = sorted(rels, reverse=True)
    denom = dcg(ideal)
    return (dcg(rels) / denom) if denom > 0 else 0.0


def evaluate(path: str = "eval/questions.jsonl", k: int = 5):
    recall, rr, ndcg, n = 0.0, 0.0, 0.0, 0
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        gold = set(item.get("gold_chunks", []))
        if not gold:  # skip out-of-scope items for retrieval metrics
            continue
        n += 1
        manual_id = resolve_manual(item.get("make"), item.get("model"),
                                   item.get("year"))
        fused = retrieve(item["question"], manual_id)
        passages, _ = rerank(item["question"], fused)
        ids = [cid for cid, _ in passages]

        if gold & set(ids[:k]):
            recall += 1
        for rank, cid in enumerate(ids):
            if cid in gold:
                rr += 1.0 / (rank + 1)
                break
        ndcg += ndcg_at_k(ids, gold, k)

    if n == 0:
        print("No in-scope items with gold_chunks found.")
        return
    print(f"n={n}  Recall@{k}={recall/n:.3f}  "
          f"MRR={rr/n:.3f}  NDCG@{k}={ndcg/n:.3f}")


if __name__ == "__main__":
    evaluate(k=SETTINGS.top_k_rerank)

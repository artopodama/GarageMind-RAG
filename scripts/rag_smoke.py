"""Phase 2 proof: exercise the full pipeline on real questions and print, for
each, the vehicle, resolved manual_id (scoping), retrieved passage count, the
reranker's top score, and the final grounded answer + citations (or refusal).

Run:  .venv/bin/python -m scripts.rag_smoke
"""
import sys

from app.config import SETTINGS
from app.retrieval.metadata import resolve_manual
from app.retrieval.hybrid import retrieve
from app.retrieval.rerank import rerank
from app.generate.answer import answer

# (question, make, model, year) — vehicles chosen to exist in whatever brands
# are indexed so far (default: Honda). Override with argv to target others.
CASES = [
    ("How do I check the engine oil level?", "Honda", "Civic", 2019),        # plain lookup
    ("What is the recommended tyre pressure?", "Honda", "Civic", 2019),      # safety-critical
    ("What is the recommended tyre pressure?", None, None, None),            # same Q, unscoped
    ("What should I do if the brake system warning light comes on?", "Honda", "Civic", 2019),
    ("How do I install a turbocharger and tune the ECU myself?", "Honda", "Civic", 2019),  # out-of-scope -> refusal
]


def run_case(question, make, model, year):
    manual_id = resolve_manual(make, model, year)
    fused = retrieve(question, manual_id)
    passages, top_score = rerank(question, fused)
    res = answer(question, make, model, year)

    veh = f"{make} {model} {year}" if make else "(no vehicle selected)"
    print("=" * 78)
    print(f"Q: {question}")
    print(f"Vehicle: {veh}")
    print(f"Scope manual_id: {manual_id}   (scoped={manual_id is not None})")
    print(f"Fused candidates: {len(fused)}   Reranked passages: {len(passages)}   "
          f"top_score={top_score:.4f}   refusal_threshold={SETTINGS.refusal_score}")
    print(f"safety_critical={res['safety_critical']}   REFUSED={res['refused']}")
    print("-" * 78)
    print(res["text"].strip())
    if res.get("sources"):
        print("-" * 78)
        print("Sources:")
        for s in res["sources"]:
            print(f"  • {s['label']}")
            if s.get("source_url"):
                print(f"    {s['source_url']}")
    print()


if __name__ == "__main__":
    if len(sys.argv) >= 4:
        q = sys.argv[1]
        mk, md = sys.argv[2], sys.argv[3]
        yr = int(sys.argv[4]) if len(sys.argv) > 4 else None
        run_case(q, mk, md, yr)
    else:
        for c in CASES:
            run_case(*c)

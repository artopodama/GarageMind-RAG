"""Phase 4: RAGAS evaluation over the labelled question set.

Computes faithfulness, answer relevancy, context precision, and context recall,
decomposing quality into retrieval vs generation contributions.

Runs fully offline: the RAGAS judge LLM is a local Ollama model (via the
OpenAI-compatible endpoint) and the embeddings are the local BGE model.

Memory note (this repo targets a 16 GB laptop): running the full retrieval
pipeline (cross-encoder reranker + 7B generator) AND the RAGAS judge in one
process OOMs. So this splits into two lean phases:

  1. --build-only : run the real pipeline, cache the (question, answer,
                    contexts, ground_truth) records to disk, then exit — freeing
                    the reranker + 7B model.
  2. --eval-only  : a fresh process that loads ONLY ragas + a small judge
                    (default qwen2.5:3b-instruct) + embeddings — no reranker.

Default (no flag) runs both in one process (fine on a bigger machine).
The small local judge is noisier than a GPT-4-class judge — treat RAGAS numbers
as indicative; run_ir.py has the harder, deterministic numbers.

Run:  python -m eval.run_ragas --build-only && \
      ollama stop qwen2.5:7b-instruct && \
      python -m eval.run_ragas --eval-only
"""
import argparse
import json
import os
import sys
import types

# ragas 0.4.3 hard-imports a langchain path removed in newer langchain-community.
# We use Ollama, never Vertex AI, so shim the symbol so the import succeeds.
_shim = types.ModuleType("langchain_community.chat_models.vertexai")
_shim.ChatVertexAI = type("ChatVertexAI", (), {})
sys.modules["langchain_community.chat_models.vertexai"] = _shim

from app.config import SETTINGS  # noqa: E402

CACHE = "eval/_ragas_records.json"
JUDGE_MODEL = os.getenv("RAGAS_JUDGE_MODEL", "qwen2.5:3b-instruct")


def build_records(path: str = "eval/questions.jsonl") -> list[dict]:
    # Heavy imports (reranker, embeddings, generator) stay local so --eval-only
    # never loads them.
    from app.generate.answer import answer
    from app.retrieval.metadata import resolve_manual
    from app.retrieval.hybrid import retrieve
    from app.retrieval.rerank import rerank

    records = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        if item.get("out_of_scope"):
            continue  # RAGAS faithfulness/recall aren't defined for refusals
        res = answer(item["question"], item.get("make"),
                     item.get("model"), item.get("year"))
        manual_id = resolve_manual(item.get("make"), item.get("model"),
                                   item.get("year"))
        fused = retrieve(item["question"], manual_id)
        passages, _ = rerank(item["question"], fused)
        records.append({
            "question": item["question"],
            "answer": res["text"],
            "contexts": [t for _, t in passages],
            "ground_truth": item["answer"],
        })
    json.dump(records, open(CACHE, "w"))
    print(f"Built {len(records)} records -> {CACHE}")
    return records


def evaluate_records(records: list[dict]):
    from datasets import Dataset
    from ragas import evaluate
    from ragas.run_config import RunConfig
    from ragas.metrics import (
        faithfulness, answer_relevancy, context_precision, context_recall,
    )
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from langchain_openai import ChatOpenAI
    from langchain_community.embeddings import HuggingFaceEmbeddings

    llm = LangchainLLMWrapper(ChatOpenAI(
        model=JUDGE_MODEL, base_url=SETTINGS.deepseek_base_url,
        api_key=SETTINGS.deepseek_api_key, temperature=0.0, timeout=300))
    emb = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(model_name=SETTINGS.embed_model))

    ds = Dataset.from_dict({
        "question": [r["question"] for r in records],
        "answer": [r["answer"] for r in records],
        "contexts": [r["contexts"] for r in records],
        "ground_truth": [r["ground_truth"] for r in records],
    })
    print(f"Evaluating {len(ds)} items with local judge ({JUDGE_MODEL}), "
          f"serialized (max_workers=1)...")
    report = evaluate(
        ds,
        metrics=[faithfulness, answer_relevancy,
                 context_precision, context_recall],
        llm=llm, embeddings=emb,
        run_config=RunConfig(max_workers=1, timeout=300),
    )
    print(report)
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-only", action="store_true")
    ap.add_argument("--eval-only", action="store_true")
    args = ap.parse_args()

    if args.eval_only:
        recs = json.load(open(CACHE))
        evaluate_records(recs)
    elif args.build_only:
        build_records()
    else:
        evaluate_records(build_records())

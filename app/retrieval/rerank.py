"""Cross-encoder reranking of fused candidates.

Returns the top-k passages and the top score, which drives the refusal decision
in the generator.

Uses sentence-transformers' ``CrossEncoder`` (compatible with transformers 5.x)
rather than FlagEmbedding's ``FlagReranker`` — the latter calls a slow-tokenizer
method (``prepare_for_model``) that transformers 5 removed. Scores are
sigmoid-normalized to [0, 1], matching FlagReranker's ``normalize=True``, so the
configured ``REFUSAL_SCORE`` threshold keeps the same meaning.
"""
import math

from sentence_transformers import CrossEncoder

from app.config import SETTINGS

_reranker = CrossEncoder(
    SETTINGS.reranker, max_length=512, device=SETTINGS.embed_device
)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def rerank(query: str, candidates: list[tuple[str, str]]):
    if not candidates:
        return [], 0.0
    pairs = [[query, txt] for _, txt in candidates]
    raw = _reranker.predict(pairs)  # numpy array of relevance logits
    scores = [_sigmoid(float(s)) for s in raw]
    ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
    top = ranked[: SETTINGS.top_k_rerank]
    top_score = float(ranked[0][1]) if ranked else 0.0
    return [(cid, txt) for (cid, txt), _ in top], top_score

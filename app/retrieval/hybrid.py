"""Hybrid retrieval: dense (semantic) + BM25 (lexical), fused with RRF.

Both retrievers respect the metadata scope (manual_id) so answers come
from the correct vehicle's manual.
"""
import pickle

import chromadb

from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from app.config import SETTINGS

_embed = HuggingFaceEmbedding(model_name=SETTINGS.embed_model)
_chroma = chromadb.PersistentClient(
    path=f"{SETTINGS.stores_dir}/chroma"
).get_collection("manuals")

with open(f"{SETTINGS.stores_dir}/bm25.pkl", "rb") as f:
    _bm = pickle.load(f)


def _dense(query: str, manual_id: str | None, k: int):
    where = {"manual_id": manual_id} if manual_id else None
    res = _chroma.query(
        query_embeddings=[_embed.get_text_embedding(query)],
        n_results=k, where=where,
    )
    return list(zip(res["ids"][0], res["documents"][0]))


def _bm25(query: str, manual_id: str | None, k: int):
    scores = _bm["bm25"].get_scores(query.split())
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    out = []
    for i in order:
        if manual_id and _bm["metas"][i].get("manual_id") != manual_id:
            continue
        out.append((_bm["ids"][i], _bm["texts"][i]))
        if len(out) >= k:
            break
    return out


def rrf(lists, k: int = 60):
    """Reciprocal Rank Fusion (Cormack et al., 2009)."""
    scores, text = {}, {}
    for lst in lists:
        for rank, (cid, txt) in enumerate(lst):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
            text[cid] = txt
    ranked = sorted(scores, key=scores.get, reverse=True)
    return [(cid, text[cid]) for cid in ranked]


def retrieve(query: str, manual_id: str | None):
    dense = _dense(query, manual_id, SETTINGS.top_k_dense)
    sparse = _bm25(query, manual_id, SETTINGS.top_k_bm25)
    return rrf([dense, sparse])

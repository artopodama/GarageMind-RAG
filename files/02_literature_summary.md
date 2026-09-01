# Literature Summary

Condensed from the full Literature Review document. This is the
reasoning trail for *why* the system is designed the way it is — use it
to justify design choices or to expand the Main Report's Results
discussion later.

## The core argument

1. LLMs are fluent but store knowledge parametrically → static,
   unattributable, prone to hallucination (Ji et al., 2023). Unsafe for
   maintenance advice on its own.
2. Retrieval-Augmented Generation (Lewis et al., 2020) fixes this by
   grounding generation in a non-parametric memory that can be updated
   without retraining — critical since manuals get added/revised.
3. Gao et al. (2023) taxonomy — **Naive / Advanced / Modular RAG** — is
   the organizing vocabulary for this thesis:
   - *Naive RAG* = the baseline (chunk → embed → top-k cosine → generate)
   - *Advanced RAG* = the target architecture (metadata pre-filtering,
     hybrid retrieval, reranking) — this is what we're building
   - *Modular RAG* = reserved for the optional diagnostic/reasoning mode
4. Retrieval quality bounds RAG quality. Sparse (BM25) and dense
   (DPR-style) retrieval are complementary, not competing — combine via
   Reciprocal Rank Fusion (Cormack et al., 2009), then refine with a
   cross-encoder reranker (Nogueira & Cho, 2019). Strich et al. (2026)
   confirm on table-rich technical corpora that hybrid+rerank beats any
   single-stage method, and that BM25 can beat dense retrieval on
   corpora full of exact tokens (part numbers, codes) — directly
   relevant to automotive manuals.
5. Sobhan & Haque (2025) is the **closest methodological precedent**: a
   structured-data-aware RAG pipeline for technical documents, reporting
   faithfulness/relevancy in the high-80s to mid-90s (RAGAS). Validates
   structure-aware ingestion + reranking + RAGAS evaluation as the right
   approach for this thesis.
6. A small but real automotive/industrial-maintenance RAG literature
   exists: EPSTEM (2025, automotive assistant with sentence-transformer
   retriever + cross-encoder reranker — nearly identical shape to this
   project), Harbola et al. (2025, prescriptive maintenance agents),
   Discover Computing (2025, multi-step RAG fault diagnosis), Isuzu/Graph
   RAG (2024, failure analysis).
7. Industry precedent: BMW (Alexa + LLM over manuals) and Mercedes-Benz
   MBUX both deploy documentation-grounded assistants specifically to
   suppress hallucination — validates the problem and the grounding
   approach at production scale.
8. Evaluation: RAGAS (Es et al., 2024) gives reference-free metrics
   (faithfulness, answer relevancy, context precision, context recall)
   that decompose quality into retrieval vs. generation contributions —
   essential for ablations without hand-authoring hundreds of gold
   answers. Complemented by classical IR metrics (Recall@k, MRR, NDCG@k)
   against a hand-labelled gold-passage set.

## The thesis's specific novelty claim

**Coupling a structured metadata store (MarkdownDB over YAML
front-matter) with semantic retrieval so that answers are scoped to the
correct make/model/year** — this combination is under-explored in the
surveyed automotive RAG literature, which tends to use flat semantic
retrieval only. This is the primary technical contribution claim (see
Main Report §1.4 and Literature Review §8).

## Full reference list (keys used across all documents, in `scripts/refs.js`)

lewis2020, karpukhin2020, guu2020, izacard2021, izacard2023, asai2024,
gao2023, yu2024, epstem2025, harbola2025, hilgpt2025, discover2025,
graphrag2024, sobhan2025, es2024, reimers2019, muennighoff2023,
xiao2024, chen2024, malkov2020, robertson2009, cormack2009, deepseekv3,
deepseekr1, vaswani2017, brown2020, devlin2019, ji2023, nogueira2019,
strich2026, langchain, llamaindex, markdowndb (34 entries total). Full
bibliographic details are in `scripts/refs.js` and rendered in every
document's References section.

## Key numeric anchors to remember

- Sobhan & Haque (2025): faithfulness ~94%, used as an external
  reference band (NOT a target — corpora differ) for this thesis's
  results.
- DeepSeek-V3: Mixture-of-Experts, 671B total params, ~37B activated per
  token, Multi-head Latent Attention.
- DeepSeek-R1: published in *Nature*, RL-trained explicit chain-of-thought
  reasoning.

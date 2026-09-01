# Architecture Decisions

The system has four sequential layers plus one cross-cutting concern.
This file records what each layer does and *why* it's designed that
way — the reasoning a supervisor would ask about.

## Layer A — Data Acquisition

**What:** Collect manual content from mycarusermanual.com.

**⚠️ CORRECTED MID-PROJECT:** originally assumed the site serves
downloadable PDF manuals. It does not. See `04_data_source_findings.md`
for the full, verified truth. The architecture and code below reflect
the corrected (HTML-based) reality.

**Current design:** an async HTTP crawler (`httpx` + `BeautifulSoup`,
NOT a headless browser — content is in the raw HTML, no JS rendering
needed) fetches each vehicle's "generation page," which conveniently
lists every topic-page URL for that manual in one response. Those topic
pages are then fetched individually. Everything is cached to disk by
URL so crawls are resumable, and every request is gated by a
`robots.txt` check.

## Layer B — Ingestion and Indexing

**What:** Turn raw pages into two aligned representations: (1) a
semantic vector index, and (2) a structured metadata index.

**Why two representations:** the vector DB answers "which passages are
semantically about this question?" while MarkdownDB answers "which
manual, and which section, is this question even allowed to draw from?"
Keeping these separate is what lets the system return the tyre pressure
for the *correct model year* rather than a plausible-sounding value from
a different vehicle. This separation is the thesis's core novelty claim.

**Current design (corrected):** each HTML topic page is converted
directly to a Markdown file with YAML front-matter. Make, model, body
style, year, section, and subsection are parsed **from the URL and
breadcrumb**, not inferred from document text — the URL structure gives
this almost for free (see `04_data_source_findings.md`). No PDF parsing,
no OCR, no table-extraction library needed, because there are no PDFs
and no scanned pages. Because the site's own information architecture
already segments a manual into ~100–150 single-topic pages, each
resulting Markdown file is already close to an ideal retrieval chunk —
the "structure-aware chunking" concern from the literature is largely
solved by the source format itself, rather than needing to be solved by
a custom chunker.

MarkdownDB (`mddb`, Node.js) then scans this Markdown corpus and builds
a queryable SQLite index over the front-matter fields. It runs as a
side-process; Python reads its SQLite output directly. This
file-based contract avoids needing a live cross-language bridge.

Chunks are embedded (BGE-large or similar) into Chroma (HNSW), and the
same chunk text populates a parallel BM25 index.

## Layer C — Retrieval and Ranking

**What:** Turn a question into a small, high-precision passage set.

**Steps, in order:**
1. **Metadata filter** — if make/model/year is known, resolve it via
   MarkdownDB to a `manual_id` and scope everything downstream to that
   manual only.
2. **Hybrid retrieval** — dense (semantic, ANN over the vector index)
   and sparse (BM25, lexical) run in parallel within the scoped set.
3. **Fusion** — Reciprocal Rank Fusion (RRF) merges the two ranked lists
   without needing to normalize incomparable similarity/BM25 scores.
4. **Reranking** — a cross-encoder re-scores the fused top ~20–50
   candidates and keeps the top few; the top score also drives the
   refusal decision (below threshold → refuse).

**Why hybrid, not dense-only:** automotive manuals are dense with exact
tokens (part numbers, warning-lamp names, DTC-style codes) that BM25
catches and dense embeddings can miss; the literature (Strich et al.,
2026) confirms hybrid beats single-stage on this kind of corpus.

## Layer D — Generation and Grounding

**What:** Produce a cited, safe answer or an explicit refusal.

**Design:** the orchestrator assembles a prompt containing the question,
the reranked passages (each tagged with its source), and a system
instruction mandating: (1) answer only from CONTEXT, (2) cite the source
per claim, (3) if CONTEXT lacks the answer, emit the exact refusal
string, (4) never guess safety-critical values (pressures, torques,
capacities, fluid types). DeepSeek-V3 (`deepseek-chat`) handles direct
questions; DeepSeek-R1 (`deepseek-reasoner`) is reserved for an optional
multi-step diagnostic mode. Refusal is a first-class outcome, not an
error — it's measured during evaluation as desirable behaviour on
out-of-scope questions.

## Cross-cutting: Evaluation

Runs as an independent harness, not embedded in the pipeline:
- **RAGAS** (faithfulness, answer relevancy, context precision, context
  recall) over a hand-authored question set.
- **Classical IR metrics** (Recall@k, MRR, NDCG@k) against hand-labelled
  gold passages, isolating retrieval from generation.
- **Ablations**: dense-only vs hybrid vs hybrid+rerank; scoped vs
  unscoped; chunk size variants; embedding model variants — each is just
  a config change + a harness rerun, because every stage sits behind a
  narrow interface (`retrieve()`, `rerank()`, `generate()`,
  `resolve_manual()`).
- **Safety review**: a curated set of safety-critical and out-of-scope
  questions gets manual review, checking grounding and refusal
  correctness.

## Framework role division (LlamaIndex vs LangChain)

- **LlamaIndex** owns ingestion, indexing, and retrieval — the core QA
  path. Chosen for minimal code and native structure-aware chunking /
  hybrid retrieval support.
- **LangChain / LangGraph** is introduced ONLY for the optional agentic
  diagnostic mode (multi-step reasoning combining several manual facts).
  The core path does not need it.

## Component/deployment shape (reference implementation)

A thin client (Streamlit or CLI) → FastAPI application → RAG
orchestrator (LlamaIndex) + retriever/reranker/ingestion/eval modules →
three persistent stores (vector DB, MarkdownDB SQLite, filesystem
corpus) → two externals (DeepSeek API, the source website). MarkdownDB
runs as a Node.js side-process; its SQLite output file is the
integration surface with Python.

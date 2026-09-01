# GarageMind — RAG Automotive Maintenance Assistant

A Retrieval-Augmented Generation (RAG) system that answers vehicle maintenance
questions in natural language by grounding an open-weight LLM in a corpus of
owner's manuals. Every answer is drawn **only** from retrieved manual passages,
**cites its source**, and the system **refuses** rather than guess when the
manual does not contain the information — especially for safety-critical values
(tyre pressure, torque, fluid capacities/types).

Reference implementation for the thesis
**"RAG-Enhanced LLMs for Automotive Maintenance Support Systems."**

> **Runs fully locally, no API keys.** Generation uses a local **Ollama** model
> (`qwen2.5:7b-instruct`) via its OpenAI-compatible endpoint. To use the hosted
> DeepSeek model instead, just point `.env` at it (see below).

---

## Architecture at a glance

```
crawl HTML (mycarusermanual.com)  ->  Markdown + YAML front-matter
   data/manuals/<brand>/<model>/<variant>/<section>/<sub>.md   (already crawled: 51k files)

   ├─ manifest.py   derive make / year-range / manual_id from the path
   │                -> data/stores/manuals.sqlite         (metadata scoping bridge)
   └─ build_index.py  chunk (Markdown-structure + size-bounded) -> BGE embeddings
                    -> Chroma (dense)  +  BM25 (lexical)   in data/stores/

question + (make, model, year)
   -> resolve_manual()  -> manual_id                       (scope to the right vehicle)
   -> hybrid retrieve   dense + BM25, fused with RRF, filtered by manual_id
   -> cross-encoder rerank (bge-reranker-v2-m3)
   -> refuse if top score < threshold OR the context doesn't answer
   -> else  local LLM (Ollama)  grounded + cited  ->  answer
```

- **Metadata bridge (`app/ingest/manifest.py`):** the crawled front-matter has
  `brand`/`model`/`variant` but no `make`/`year`/`manual_id` — which retrieval
  scopes on. This derives them deterministically from the on-disk path
  (`brand`→`make` alias, year range parsed from the variant) into
  `data/stores/manuals.sqlite`. `app/retrieval/metadata.py` resolves
  `(make, model, year)` → `manual_id` against it. (Replaces the unverified
  MarkdownDB-schema guess; `mddb/` is kept but optional.)
- **Indexing (`app/ingest/build_index.py`):** reads `data/manuals/` **in place**
  (no copy of the 18 GB tree), injects the scope metadata into every chunk, and
  builds Chroma + BM25 **brand-by-brand, resumably** (a finished brand is
  skipped on re-run; deterministic content-hash chunk ids; disk guard).
- **Retrieval:** hybrid dense + BM25 with Reciprocal Rank Fusion, scoped by
  `manual_id`, then a cross-encoder reranker (`app/retrieval/rerank.py`, via
  sentence-transformers `CrossEncoder`).
- **Generation (`app/generate/answer.py`):** provider-agnostic OpenAI client →
  local Ollama by default. Grounds every claim in the retrieved context, cites
  `[Make Model - Section]`, and emits a hard refusal below the reranker
  threshold.
- **API + UI:** FastAPI (`app/api.py`) exposes `/ask`, `/health`, `/vehicles`,
  and serves the **GarageMind web UI** (`web/`) at `/` — a real chat interface
  wired to `/ask` with citation chips, an expandable source excerpt + deep link,
  a safety-critical trust indicator, and a calm amber refusal card.
- **Evaluation (`eval/`):** `run_ir.py` (Recall@k / MRR / NDCG@k against
  independently-derived gold passages) and `run_ragas.py` (faithfulness / answer
  relevancy / context precision / recall, judged by the local model).

---

## Requirements

- **Python 3.11** (the ML stack lags on 3.13; use 3.11)
- **[Ollama](https://ollama.com)** with a chat model pulled
  (`ollama pull qwen2.5:7b-instruct`)
- ~5 GB disk for the embedding + reranker models on first run
- Node.js is **not** required for the core pipeline (only for the optional
  `mddb/` MarkdownDB index)

---

## Quick start

```bash
# 1. Environment (Python 3.11)
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Local model (Ollama)
ollama serve &                       # ensure OLLAMA_MODELS points at a mounted path
ollama pull qwen2.5:7b-instruct
cp .env.example .env                 # defaults already target Ollama; edit to use DeepSeek

# 3. Index (the corpus already exists under data/manuals/)
make manifest                        # build the metadata bridge (data/stores/manuals.sqlite)
make index-brand BRANDS=honda        # index one brand (fast) …
# make index                         # … or ALL brands (long; resumable, brand-by-brand)

# 4. Ask
make serve                           # API + UI at http://127.0.0.1:8000/
#   UI:        http://127.0.0.1:8000/
#   API docs:  http://127.0.0.1:8000/docs

# 5. Evaluate
make eval-ir                         # retrieval metrics (Recall@k / MRR / NDCG)
make eval                            # RAGAS (local judge)
```

`.env` (created for you) points generation at Ollama:

```
DEEPSEEK_API_KEY=ollama
DEEPSEEK_BASE_URL=http://localhost:11434/v1
GEN_MODEL=qwen2.5:7b-instruct
EMBED_MODEL=BAAI/bge-small-en-v1.5
RERANKER=BAAI/bge-reranker-v2-m3
EMBED_DEVICE=mps
```

Ask via the API:

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What is the recommended tyre pressure?",
       "make":"Honda","model":"Civic","year":2019}'
```

See `web/API.md` for the full `/ask` response shape.

---

## Current status (what actually runs)

Verified end-to-end in this build:

- Metadata bridge, dense + lexical index, **scoped** hybrid retrieval,
  cross-encoder rerank, grounded generation with citation, and hard refusal.
- FastAPI `/ask` + `/health` + `/vehicles`, and the web UI wired to the real
  backend (grounded answer + citation + amber refusal all render from `/ask`).

**Corpus indexed in this session:** **Honda** — 9 manuals across Civic, CR-V,
Accord, HR-V (~6,992 chunks). The full corpus (**51,014 files / 427 variants /
32 brands / 18 GB**) is on disk under `data/manuals/`; `make index` builds every
brand, resumably. On a 16 GB / MPS laptop, embedding *everything* is a
multi-hour (~overnight) unattended job — run it in the background; it is
resumable and stops gracefully if disk runs low.

**Evaluation (Honda set — `eval/questions.jsonl`, 12 questions, 9 in-scope):**

| Metric | Value | Notes |
|---|---|---|
| **Recall@5** | **1.000** | retrieval (deterministic) |
| **MRR** | **0.944** | retrieval (deterministic) |
| **NDCG@5** | **0.959** | retrieval (deterministic) |
| RAGAS answer-relevancy | 0.68 | local judge |
| RAGAS context-precision | 0.98 | local judge |
| RAGAS faithfulness | n/a | local-judge parse failure (see below) |
| RAGAS context-recall | n/a | local-judge parse failure (see below) |

Retrieval is strong on this small, illustrative set: the scoped hybrid+rerank
pipeline surfaces the correct passage in the top 5 every time (Recall@5 = 1.0),
usually at rank 1 (MRR 0.94). These are the hard, deterministic numbers.

The RAGAS answer-relevancy (0.68) and context-precision (0.98) come out solid.
**Faithfulness and context-recall return `n/a`**: the local Ollama judge (tried
at both 3B and 7B) does not reliably emit the strict JSON those two metrics'
output parsers require (~50 parse failures), so RAGAS reports NaN. This is a
known limitation of small local judges — a GPT-4-class judge would score them —
not a pipeline fault. It is why `run_ir.py`'s deterministic metrics are treated
as the primary quantitative result. (This is a demonstration set, not the full
100–200-item thesis corpus.)

---

## Deviations from the original plan (and why)

- **Local Ollama generation** (`qwen2.5:7b-instruct`) instead of the DeepSeek
  API — no key needed, fully offline. DeepSeek still works: set `DEEPSEEK_*` in
  `.env`.
- **`bge-small-en-v1.5` embeddings** instead of `bge-large` — bge-large
  thrashed swap on 16 GB RAM (embedding rate collapsed ~10×). The small
  bi-encoder + the cross-encoder reranker (which does the precision work) keeps
  retrieval quality high at a fraction of the memory.
- **sentence-transformers `CrossEncoder`** for reranking instead of
  FlagEmbedding's `FlagReranker` — the latter calls a tokenizer method removed
  in transformers 5.x.
- **In-place indexing over `data/manuals/`** with a SQLite **manifest** bridge,
  instead of aggregating into a flat `data/markdown/` + MarkdownDB — avoids
  duplicating 18 GB and sidesteps the unverified `mddb` schema.
- **Deterministic content-hash chunk ids** so brand builds are safely
  restartable.

---

## Known limitations & next steps

- **Coverage:** only Honda is indexed here — run `make index` for the full set.
- **Extraction noise:** the crawled Markdown has HTML-extraction spacing
  artifacts ("kP a", "vehi c le"). Dense retrieval + rerank tolerate it; BM25
  (exact-token) is hurt more. A text-cleanup pass would lift lexical recall.
- **Year gaps:** `resolve_manual` returns `None` (unscoped) when no variant
  covers the requested year (e.g. there is no 2020 Corolla variant). The
  `/vehicles` endpoint exposes the actual indexed variants; the UI selector
  could be driven from it to only offer answerable vehicles.
- **RAGAS judge:** uses the local 7B model — noisier than a GPT-4-class judge;
  treat those numbers as indicative. `run_ir.py` metrics are the harder numbers.
- **BM25 at full scale:** BM25Okapi holds the whole tokenized corpus in RAM; for
  all ~500k chunks consider a disk-backed lexical index or dense-only retrieval.

---

## Project layout

```
app/
  config.py              # settings (models, hyper-params, paths) via env / .env
  ingest/
    manifest.py          # metadata bridge: (make,model,year) -> manual_id  [NEW]
    build_index.py       # in-place chunk + embed + index (Chroma + BM25), resumable
    crawl.py, parse_html.py, to_markdown.py, run.py   # corpus crawler (already run)
  retrieval/
    metadata.py          # resolve_manual() over manuals.sqlite
    hybrid.py            # dense + BM25 + RRF, scoped by manual_id
    rerank.py            # cross-encoder reranker
    citations.py         # chunk-id -> human-readable source  [NEW]
  generate/answer.py     # grounded generation + refusal (Ollama / DeepSeek)
  api.py                 # FastAPI /ask, /health, /vehicles; serves web/
  ui.py                  # (legacy Streamlit UI)
web/                     # GarageMind chat UI (HTML/CSS/JS), wired to /ask; see API.md
eval/
  questions.jsonl        # labelled question set (gold via derive_gold.py)
  derive_gold.py         # fills gold_chunks by content match  [NEW]
  run_ir.py, run_ragas.py
mddb/build.mjs           # optional MarkdownDB index (Node)
data/manuals/            # crawled corpus (git-ignored)
data/stores/             # manuals.sqlite, chroma/, bm25.pkl, chunks.sqlite (git-ignored)
```

---

## Reproducibility

- All model ids and hyper-parameters live in `app/config.py` / `.env`.
- Generation uses `temperature=0.0`.
- `make manifest && make index` rebuilds every index from `data/manuals/`.
- Chunk ids are deterministic (content hash), so re-runs are idempotent.

## Ethics & legal

Owner's manuals are copyrighted works of vehicle manufacturers. This project
uses them **only** for non-commercial academic research, honours `robots.txt`,
identifies its crawler honestly, rate-limits requests, collects no personal
data, and **does not redistribute** the corpus.

## Safety

Maintenance advice can be safety-critical. The system cites sources and
**refuses rather than guesses**, and never invents pressures, torques,
capacities, or fluid types. Safety-critical answers should be manually reviewed.

## License

Code: MIT. Corpus: not included and not redistributable.

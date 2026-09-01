# Implementation Status

Precise, current inventory of the runnable reference implementation.
Source lives at `/home/claude/thesis/code/rag-automotive/` and is
packaged as `rag-automotive-code.zip` in outputs. **All Python files
compile clean** (`py_compile` verified as of the last update).

## File-by-file status

### Root
- `README.md` — full setup/usage docs, updated for the HTML-crawl
  reality (not PDF). Covers quick start, corpus-building at 3 scales,
  project layout, reproducibility, ablation guidance, ethics/safety.
- `requirements.txt` — updated: removed `pymupdf`, `pdfplumber`,
  `pytesseract`, `playwright`, `scrapy`, `markdownify`; added `httpx`,
  `beautifulsoup4`, `lxml`.
- `Makefile` — one-command workflows: `setup`, `corpus`,
  `corpus-broad N=<n>`, `mddb`, `index`, `ingest` (= corpus+mddb+index),
  `serve`, `ui`, `eval`, `eval-ir`, `clean`.
- `.env.example` — DeepSeek key/URL, model IDs, chunking/retrieval
  hyper-parameters, all read by `app/config.py`.
- `.gitignore` — excludes `data/`, `.env`, caches, `node_modules/`.

### `app/config.py`
Centralised, environment-driven settings (`Settings` dataclass): DeepSeek
key/base URL/model IDs (`gen_model`, `reason_model`), embed/reranker
model names, chunk size/overlap, retrieval top-k values, refusal score
threshold, data paths. **Status: complete, unchanged since first
written.**

### `app/ingest/` — DATA COLLECTION (rewritten mid-project)

- **`crawl.py`** — async HTTP crawler for the site's HTML pages. Key
  pieces: `allowed()` (robots.txt gate), `fetch()` (disk-cached,
  rate-limited GET), `parse_make_links/parse_model_links/
  parse_generation_links/parse_subsection_links()` (BeautifulSoup
  selectors matching the site's URL hierarchy), `ManualTarget`
  dataclass (make/model/body_style/year_key → derived `generation_path`
  and `manual_id`), `collect_manual()` (fetch one manual's generation
  page as a manifest, then every subsection page it lists),
  `collect_many()` (bounded-concurrency collection across several
  manuals). Includes a `__main__` block with a 3-vehicle example.
  **Status: complete, compiles clean.**
- **`discover.py`** — enumerate makes/models/generations programmatically
  instead of hand-typing URLs: `list_makes()`, `list_models()`,
  `list_generations()`, `sample_one_generation_per_make()` (breadth-first
  sampling: N models from each requested make, most recent generation).
  **Status: complete, compiles clean.**
- **`to_markdown.py`** — HTML → Markdown converter (REPLACES the deleted
  PDF path entirely). `extract_main_content()` pulls the `<h1>` title and
  walks siblings until a "Related Topics"/"Popular Owner Manuals"/
  "Latest Owner Manuals" boilerplate marker, converting `<table>` to
  Markdown tables and `<p>/<li>/<h2-4>` to text. `parse_breadcrumb_
  metadata()` derives make/model/body_style/year_key/section/subsection
  straight from the URL (not from document text). `write_page()` writes
  one front-mattered `.md` file per subsection under
  `data/markdown/<manual_id>/<slug>.md`. `write_manual()` writes every
  page collected for one manual. **Status: complete, compiles clean.**
- **`build_corpus.py`** — orchestrator tying `crawl` + `to_markdown`
  together; the actual "download everything into files" entry point.
  `DEFAULT_SAMPLE` = 5 hand-picked vehicles across different makes
  (Toyota Corolla, Honda Civic, VW Golf, Ford Focus, BMW 3-Series).
  `run()` collects+writes a target list with bounded concurrency.
  `run_broad(n_makes, models_per_make)` uses `discover.py` to
  auto-select targets. CLI: `python -m app.ingest.build_corpus` (sample)
  or `--broad N` (auto-discovered). **Status: complete, compiles clean.**
- **`build_index.py`** — chunk (LlamaIndex `MarkdownNodeParser`), embed
  (HuggingFace/BGE), upsert into Chroma, and build a parallel BM25 index
  pickled to disk. `load_docs()` was updated to `rglob("*.md")` (was
  `glob`) to walk the new nested `data/markdown/<manual_id>/*.md` layout
  produced by `to_markdown.py`. **Status: complete, compiles clean,
  updated for new directory layout.**
- ~~`parse_pdf.py`~~ — **DELETED.** No longer needed; the source has no
  PDFs. (Was: PyMuPDF text extraction + Tesseract OCR fallback +
  pdfplumber table extraction.)

### `app/retrieval/` — unchanged by the HTML-vs-PDF correction
- **`metadata.py`** — `resolve_manual(make, model, year)` queries
  MarkdownDB's SQLite output (`data/stores/markdown.db`) via
  `json_extract` on a `metadata` JSON column, returns `manual_id`.
  Falls back to `None` (no scoping) on schema mismatch rather than
  crashing. **Status: complete, compiles clean. NOTE: exact
  table/column names depend on the installed `mddb` version's schema —
  flagged as needing adjustment against a real `mddb` install.**
- **`hybrid.py`** — `_dense()` (Chroma query with metadata `where`
  filter), `_bm25()` (score + manual_id filter), `rrf()` (Reciprocal
  Rank Fusion, k=60 default), `retrieve()` (runs both, fuses). **Status:
  complete, compiles clean.**
- **`rerank.py`** — `FlagReranker` (BGE cross-encoder) wraps
  `compute_score()`, returns top-k passages + top score for the refusal
  decision. **Status: complete, compiles clean.**

### `app/generate/answer.py`
`SYSTEM` prompt (context-only answering, mandatory citation format,
exact refusal string, no-guessing rule for safety-critical values).
`answer()` resolves manual → retrieves → reranks → refuses if below
threshold or no passages → else calls DeepSeek (`gen_model` or
`reason_model` if `reasoning=True`) with `temperature=0.0`. **Status:
complete, compiles clean, unchanged by the HTML-vs-PDF correction.**

### `app/api.py` / `app/ui.py`
FastAPI `/ask` POST endpoint + `/health`; Streamlit UI with
make/model/year inputs, a reasoning-mode toggle, and citation display.
**Status: complete, compiles clean, unchanged.**

### `mddb/`
`build.mjs` (Node.js, calls `mddb`'s `MarkdownDB.indexFolder()` over
`data/markdown`, writes `data/stores/markdown.db`) + `package.json`.
**Status: complete. NOTE: not yet run against a real `mddb` install to
confirm the exact SQLite schema — see open questions.**

### `eval/`
- `run_ragas.py` — builds a HF `Dataset` from `questions.jsonl` by
  running the live pipeline, computes faithfulness/answer_relevancy/
  context_precision/context_recall via `ragas.evaluate()`.
- `run_ir.py` — Recall@k/MRR/NDCG@k against `gold_chunks` in the test
  set, skipping `out_of_scope` items.
- `questions.jsonl` — 5 illustrative sample rows (tyre pressure, oil
  grade, warning light, timing belt, an out-of-scope brake-bleed
  question) — **placeholder scale only; the real thesis test set (100–
  200 items per the Analysis Report) has not been authored yet.**
**Status: scripts complete and compile clean; question set is a small
placeholder, not the real evaluation corpus.**

## What has NOT been built/run yet

- No real corpus has actually been downloaded (the crawler has never
  been executed against the live site in this session — only
  individual pages were fetched manually during research/verification).
- No vector index or MarkdownDB SQLite file has actually been built.
- No end-to-end answer has actually been generated (no DeepSeek API key
  configured in this environment).
- No evaluation numbers exist yet — RAGAS/IR metrics are unrun.
- The `questions.jsonl` test set is 5 illustrative rows, not the
  100–200-item labelled set the Analysis Report specifies.
- MarkdownDB's actual SQLite schema has not been verified against a real
  `mddb` install — `metadata.py`'s query is a best-effort guess flagged
  for adjustment.

In short: **the code is complete, internally consistent, and compiles,
but nothing has been executed end-to-end yet.** That's the next phase.

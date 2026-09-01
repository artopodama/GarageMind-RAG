# Decisions Log

Chronological record of decisions, confirmations, and corrections made
over the course of the project. Newer entries at the bottom. Use this to
understand *why* something is the way it is, not just *what* it is.

---

**1. Initial scope confirmation (via clarifying Q&A at project start)**
- Chose a **runnable reference implementation** over mock/illustrative
  code.
- Chose to **start the thesis at ~20 pages** (skeleton) rather than
  padding to 40 immediately — expand only once real code/results exist.
- Confirmed **MarkdownDB + a separate vector DB (Chroma)** as a hybrid
  approach: MarkdownDB for structured metadata, vector DB for semantic
  search (MarkdownDB itself is explicitly NOT a vector database).
- User asked for multiple documents (report, architecture, literature
  review, structural/analytical breakdown, analysis report) "and
  anything else needed."

**2. Research phase — established the literature foundation**
- Ran extended web research; identified ~30 anchor references (Lewis
  2020, Gao 2023, Sobhan & Haque 2025 as closest methodological twin,
  RAGAS/Es 2024, DeepSeek technical reports, automotive-RAG papers,
  etc.).
- **First (incorrect) finding at this stage:** assumed
  mycarusermanual.com serves manuals as PDF downloads → this drove an
  ingestion design around PyMuPDF + OCR + pdfplumber. **This assumption
  was later proven wrong — see entry 6 below.**

**3. Document generation — built the full six-document set**
- Built a shared Node.js/docx-js styling library (`scripts/lib.js`) and
  a central bibliography module (`scripts/refs.js`) so every document
  shares consistent formatting and citations.
- Generated: Literature Review, Main Report, System Architecture,
  Implementation Plan, Analysis & Planning Report, Executive Summary
  (the last two were proactively added beyond the literal request,
  along with the code package and standalone diagram PNGs).
- Built four SVG→PNG architecture diagrams (system architecture,
  ingestion pipeline, query sequence, deployment view) plus a Gantt
  timeline — all hand-drawn as SVG (not AI-generated images) using a
  shared palette (navy #1F3A5F, green #2E5E4E accents).
- All 6 `.docx` files passed XSD validation
  (`/mnt/skills/public/docx/scripts/office/validate.py`).

**4. Quality issue found and fixed: SVG rasterisation**
- Initial SVG→PNG conversion (via `sharp`) failed with an XML parse
  error: unescaped `&` characters in labels like "Crawl & collect" and
  nested double-quotes in `font-family="Calibri, "Segoe UI"..."`.
  Fixed by adding an `esc()` helper (escapes `&`/`<`/`>`) and switching
  `font-family` to a comma-list without inner quotes.

**5. Quality issue found and fixed: diagram connector clutter**
- The first renders of the system-architecture diagram (Layer B) and
  the deployment-view diagram had overlapping/crossing connector lines.
  Rewrote the connector paths as clean orthogonal routes in both SVGs;
  confirmed visually clean on re-render.

**6. MAJOR CORRECTION — the site does not serve PDFs**
- User asked for "an easier way to download all the files" from
  mycarusermanual.com, since the assumed PDF corpus felt large/unwieldy.
- Direct verification (fetching the live site) revealed the original
  assumption was **wrong**: the site publishes each manual as ~100–150
  small per-topic **HTML** pages, not PDFs. Confirmed by fetching the
  home page, a make page (`/toyota`), a model page (`/toyota/corolla`),
  a generation page (`/toyota/corolla/4-door/2023` — which lists every
  subsection URL), and an actual content page (tire-inflation-pressure
  procedure, plain readable text).
- This is genuinely good news: it removes the biggest architectural risk
  (PDF/table extraction quality) and simplifies ingestion substantially
  (no OCR, no headless browser, metadata comes nearly free from the
  URL). Full detail in `04_data_source_findings.md`.
- **Action taken:** rewrote the entire ingestion path in the code
  package: deleted `parse_pdf.py`; rewrote `crawl.py` (async HTTP + BS4
  instead of Playwright + PDF download); wrote new `discover.py`
  (enumerate makes/models/generations); rewrote `to_markdown.py`
  (HTML→Markdown instead of PDF-pages→Markdown, metadata parsed from
  URL); wrote new `build_corpus.py` (orchestrator); fixed
  `build_index.py`'s doc loader for the new nested directory layout;
  updated `requirements.txt` (dropped pymupdf/pdfplumber/pytesseract/
  playwright/scrapy, added httpx/beautifulsoup4/lxml); rewrote the
  `Makefile` with `corpus` / `corpus-broad N=<n>` targets; rewrote the
  relevant README sections. Repackaged and re-verified
  `rag-automotive-code.zip` (all files `py_compile` clean).
- **NOT yet done:** the System Architecture and Implementation Plan
  `.docx` documents still describe the OLD PDF/OCR-based ingestion path
  in their text and code listings. They have not been regenerated to
  match the corrected code. **This is the single most important open
  task** — see `08_open_questions_next_steps.md`.

**7. User requested a practical, low-effort collection workflow**
- Clarified further: user wants an easy way to actually get data into
  "their database" (i.e., the vector index + MarkdownDB), not just
  architectural advice.
- Delivered: three clearly-scaled entry points (`make corpus` for a
  ~5-vehicle sample, `make corpus-broad N=<n>` for auto-discovered
  breadth, or a hand-written target list) — all resumable via on-disk
  HTML caching (`data/raw/html_cache/`) and logged to
  `data/raw/crawl_manifest.jsonl`. Explicitly advised against "download
  the entire site" as a goal, given the scale reality (tens of thousands
  of vehicles).

**8. This knowledge base was created**
- User asked for a folder of markdown files capturing all research and
  work so a future Claude session has full context without needing the
  raw chat history. This folder is the result.

# Open Questions and Next Steps

## Highest priority

1. **Regenerate the outdated Word documents.** `03_System_Architecture.docx`
   and `04_Implementation_Plan.docx` still describe PDF/OCR-based
   ingestion; the code has moved on. Fix by editing
   `scripts/02_architecture.js` and `scripts/04_implementation.js` (swap
   the PDF/OCR narrative and code listings for the HTML-crawl approach
   documented in `04_data_source_findings.md` and
   `05_implementation_status.md`), then rerun them with `node
   scripts/02_architecture.js` / `node scripts/04_implementation.js`,
   re-validate with the docx XSD validator, and copy the results into
   `/mnt/user-data/outputs/`. The user was asked whether to do this and
   gave no explicit preference on ordering — it's still outstanding.
   Minor touch-ups also needed in `03_main_report.js` (§5.1 OCR mention)
   and `05_analysis_report.js` (risk register top row).
2. **If the diagrams are regenerated too**, edit `scripts/diagrams.js`
   (Layer A/B box labels: "PDF fetch + robots check" → "HTML fetch +
   robots check", "Raw PDF store" → "Raw HTML cache", "PDF Parser
   (PyMuPDF · OCR fallback)" → "HTML → Markdown", etc.), rerun
   `node scripts/diagrams.js && node scripts/rasterize.js`, and
   re-embed in the regenerated documents.

## Not yet executed (code exists but is untested against the live system)

3. **No corpus has actually been downloaded yet.** The crawler
   (`app/ingest/crawl.py` / `build_corpus.py`) has been written and
   compiles, but has never been run end-to-end in this environment. Real
   next step: `make setup && make corpus` (or `corpus-broad N=5` for a
   quick first pass) and confirm it actually produces sane Markdown
   files.
4. **MarkdownDB's SQLite schema is unverified.** `app/retrieval/
   metadata.py`'s query (`json_extract(metadata, '$.make')` etc.)
   against a `files` table is a best-effort guess at `mddb`'s actual
   schema. Must be checked against a real `mddb` install
   (`cd mddb && npm install && node build.mjs` on a small sample corpus,
   then inspect `data/stores/markdown.db` with a SQLite browser) and the
   query adjusted if the real column/table names differ.
5. **No vector index has been built, no answer has been generated, no
   evaluation has been run.** All of Phase 3 (RAG core) and Phase 4
   (evaluation) in the Analysis Report's timeline are still ahead.
6. **The real evaluation question set doesn't exist yet.**
   `eval/questions.jsonl` currently has 5 illustrative rows. The
   Analysis Report specifies 100–200 hand-labelled items spanning
   factual lookups, procedures, warning-lamp questions, cross-vehicle
   disambiguation, and deliberate out-of-scope items, each annotated
   with supporting gold passages for the in-scope ones.

## Unresolved factual gaps

7. **`robots.txt` content was never actually confirmed.** Research
   attempts to fetch `https://www.mycarusermanual.com/robots.txt`
   directly were blocked by tooling constraints (URL not in prior
   search/fetch results) and no web search surfaced its actual content.
   **A human must check this directly in a browser before running any
   real crawl at scale.** The code's `allowed()` function checks it
   programmatically at runtime and defaults to disallow-on-failure, but
   this hasn't been validated against the real file.
8. **No `sitemap.xml` was confirmed to exist or not exist** for this
   site. Worth a quick manual check — if present, it could replace or
   supplement the generation-page-as-manifest discovery approach.
9. **Corpus size decision not finalized.** `01_project_overview.md` and
   the code default to "a handful to a few dozen vehicles," but the
   exact target N for the actual thesis corpus hasn't been fixed. This
   should be decided based on how Phase 2 goes (time taken per manual,
   corpus quality) rather than picked in the abstract.

## Downstream, once a corpus exists

10. Populate the Results chapter of the Main Report (currently marked
    "[To be completed after implementation]").
11. Expand the Main Report from its ~20-page skeleton toward ~40 pages,
    per the original scope agreement — this should happen AFTER results
    exist, not before.
12. Run the risk-register review at each milestone (M1–M4) as specified
    in the Analysis Report §6, updating likelihood/impact ratings based
    on actual experience.
13. Decide whether the optional diagnostic/reasoning mode (FR6, "Could"
    priority, DeepSeek-R1 + LangGraph) is worth building given time
    remaining — it was explicitly scoped as lowest priority.

## Standing reminders for future sessions

- This project's data-collection philosophy is **sample, not
  exhaustive**. Don't let "more data" scope-creep past what RQ3 (cross-
  vehicle scoping) actually needs to be tested.
- Every technical claim about the data source in this knowledge base was
  **directly verified by fetching live pages**, not assumed — if the
  site changes its structure in the future, these facts should be
  re-verified before being relied on again.
- The user has previously indicated "no preference" when asked to choose
  between options — in that situation, default to doing the more
  complete/thorough option rather than the minimal one (this was the
  approach taken for "update docs + give script" and should be treated
  as a general working style for this user).

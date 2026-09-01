# Deliverables Manifest

Exact inventory of everything produced. **Note: the "⚠️ outdated" flags
below are important** — some documents describe the pre-correction
PDF-based ingestion (see `04_data_source_findings.md` and
`06_decisions_log.md` entry 6).

## User-facing outputs (`/mnt/user-data/outputs/`)

| File | Size (approx) | Status |
|---|---|---|
| `01_Literature_Review.docx` | 28 KB | ✅ Current — not affected by the PDF/HTML correction |
| `02_Main_Report.docx` | 570 KB | ✅ Current — describes the system at a level that doesn't specify PDF vs HTML parsing detail |
| `03_System_Architecture.docx` | 933 KB | ⚠️ **Outdated** — Layer A/B text and Listings 4.1–4.4 describe PDF parsing, OCR, pdfplumber tables; needs regeneration to match the HTML-crawl reality |
| `04_Implementation_Plan.docx` | 223 KB | ⚠️ **Outdated** — Listings 2.1 (requirements.txt), 5.1–5.3 (crawl/parse_pdf/to_markdown code) all show the old PDF-based approach; needs regeneration |
| `05_Analysis_Report.docx` | 160 KB | ⚠️ **Partially outdated** — the risk register's top risk ("PDF table extraction is poor") is now moot; feasibility section's technical-risk framing should be revised |
| `06_Executive_Summary.docx` | 14.5 KB | ✅ Current — high-level enough not to specify ingestion mechanics |
| `diagrams/01_system_architecture.png` | 434 KB | ⚠️ Diagram itself shows "PDF fetch + robots check" / "Raw PDF store" / "PDF Parser (PyMuPDF · OCR fallback)" labels in Layer A/B — outdated, would need regeneration if diagrams are refreshed |
| `diagrams/02_ingestion_pipeline.png` | 224 KB | ⚠️ Same — steps 2–3 say "Download PDFs" / "Parse & OCR" |
| `diagrams/03_query_sequence.png` | 161 KB | ✅ Current — query-time flow is unaffected by the ingestion correction |
| `diagrams/04_deployment_view.png` | 260 KB | ✅ Current — component/deployment view is unaffected |
| `diagrams/05_gantt.png` | 178 KB | ✅ Current — timeline phases are unaffected (though "Corpus policy (robots/ToS)" and "Crawl + download manuals" task labels are still accurate in spirit) |
| `rag-automotive-code.zip` | ~28 KB, 33 files | ✅ **Current — this is the up-to-date, corrected version** reflecting the HTML-crawl approach |

## Document generation source (`/home/claude/thesis/scripts/`)

Node.js/docx-js scripts that generate the `.docx` files. Re-running any
of these regenerates that document from scratch — this is how the
outdated documents above would be fixed.

| Script | Generates | Needs edits for the PDF→HTML correction? |
|---|---|---|
| `lib.js` | Shared styling helpers (not a document itself) | No |
| `refs.js` | Shared bibliography (not a document itself) | No |
| `01_literature_review.js` | `01_Literature_Review.docx` | No |
| `02_architecture.js` | `03_System_Architecture.docx` | **Yes** — Layer A/B sections, Listings 4.1–4.4 |
| `03_main_report.js` | `02_Main_Report.docx` | Minor — §5.1 mentions "PyMuPDF with a Tesseract OCR fallback"; should be updated for accuracy |
| `04_implementation.js` | `04_Implementation_Plan.docx` | **Yes** — Listing 2.1 (deps), 5.1–5.3 (crawl/parse/markdown code) |
| `05_analysis_report.js` | `05_Analysis_Report.docx` | Minor — risk register top row |
| `06_executive_summary.js` | `06_Executive_Summary.docx` | No |
| `diagrams.js` | The 4 architecture SVGs → PNGs | **Yes, if diagrams are refreshed** — Layer A/B labels |
| `gantt.js` | The Gantt SVG → PNG | No (task labels still accurate) |
| `rasterize.js` | Generic SVG→PNG helper (uses `sharp`) | No |

Generated intermediate files live in `/home/claude/thesis/out/` (docx)
and `/home/claude/thesis/assets/` (PNG/SVG diagrams).

## Reference implementation source (`/home/claude/thesis/code/rag-automotive/`)

The full, current, corrected code package — see
`05_implementation_status.md` for a complete file-by-file breakdown.
This is packaged as `rag-automotive-code.zip` above and IS up to date.

## This knowledge base (`/home/claude/thesis/knowledge-base/`)

| File | Purpose |
|---|---|
| `00_INDEX.md` | Entry point and reading order |
| `01_project_overview.md` | Topic, goals, RQs, scope |
| `02_literature_summary.md` | Condensed lit-review reasoning |
| `03_architecture_decisions.md` | System design + rationale |
| `04_data_source_findings.md` | Verified facts about the real data source |
| `05_implementation_status.md` | File-by-file code inventory |
| `06_decisions_log.md` | Chronological decisions/corrections |
| `07_deliverables_manifest.md` | This file |
| `08_open_questions_next_steps.md` | What's unresolved, what to do next |
| `09_glossary.md` | Acronyms/terms reference |

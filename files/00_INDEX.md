# Knowledge Base Index — RAG for Automotive Maintenance Support

This folder is a working memory of everything researched, decided, and
built for the B.Sc. Computer Science thesis **"RAG-Enhanced LLMs for
Automotive Maintenance Support Systems."** It exists so that anyone (or
any AI assistant) picking up this project later can get fully current
without re-reading an entire chat history.

**If you (Claude) are reading this at the start of a new conversation:**
read this index, then read files in the order below. Together they tell
you what the project is, what's been decided and why, what's already
been built, what's factually true about the data source, and what's
still open. Treat this folder as ground truth over any prior assumption.

## Reading order

| # | File | What it tells you |
|---|------|-------------------|
| 1 | `01_project_overview.md` | The thesis topic, goals, research questions, and scope |
| 2 | `02_literature_summary.md` | Condensed findings from the literature review — why each technique was chosen |
| 3 | `03_architecture_decisions.md` | The system design and the reasoning behind each architectural choice |
| 4 | `04_data_source_findings.md` | **Critical, verified facts** about mycarusermanual.com's real structure |
| 5 | `05_implementation_status.md` | What code exists right now, file by file, and what it does |
| 6 | `06_decisions_log.md` | Chronological log of decisions, corrections, and why they were made |
| 7 | `07_deliverables_manifest.md` | Every file produced so far and where it lives |
| 8 | `08_open_questions_next_steps.md` | What's unresolved and what to do next |
| 9 | `09_glossary.md` | Acronyms and terms used throughout (RAG, RRF, HNSW, RAGAS, etc.) |

## The one-paragraph summary

We are building a Retrieval-Augmented Generation (RAG) system that
answers automotive maintenance questions by grounding an open-weight
DeepSeek LLM in owner's-manual content scraped from
`mycarusermanual.com`. Retrieval combines a structured metadata store
(MarkdownDB, scoping answers to the correct make/model/year) with hybrid
semantic+lexical search and cross-encoder reranking. Every answer must
cite its source passage and the system must refuse when evidence is
insufficient. A full six-document thesis set (Literature Review, Main
Report, System Architecture, Implementation Plan, Analysis & Planning
Report, Executive Summary) has been drafted, along with a runnable
Python/Node reference implementation. **A major correction happened
partway through the project:** the data source does not serve PDF
manuals as originally assumed — it publishes ~100–150 small HTML pages
per vehicle — which simplified ingestion considerably and is documented
in detail in `04_data_source_findings.md`. The code has been updated to
reflect this; **the Word documents (System Architecture, Implementation
Plan) have NOT yet been updated to match** — see `08_open_questions_next_steps.md`.

## Where the actual files are

- Generated thesis documents (`.docx`): `/mnt/user-data/outputs/*.docx`
- Diagrams (`.png`): `/mnt/user-data/outputs/diagrams/`
- Runnable code package: `/mnt/user-data/outputs/rag-automotive-code.zip`
- Working source (document-generation scripts): `/home/claude/thesis/scripts/`
- Working source (reference implementation): `/home/claude/thesis/code/rag-automotive/`
- This knowledge base: `/home/claude/thesis/knowledge-base/`

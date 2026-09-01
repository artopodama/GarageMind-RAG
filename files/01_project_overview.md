# Project Overview

## Thesis topic

**Working title (original, Greek):** Χρήση RAG and enhanced LLM στην
αυτοκινητοβιομηχανία — συστήματα υποστήριξης συντήρησης
**English:** Using RAG and enhanced LLMs in the automotive industry for
maintenance support systems — published/working title used across
documents: **"RAG-Enhanced LLMs for Automotive Maintenance Support
Systems."**

**Degree:** B.Sc. Computer Science, final-year/exams thesis.

## The problem

Vehicle owner's manuals are long and hard to search. Owners and
technicians need fast, correct, specific answers (tyre pressure, oil
grade/capacity, warning-light meaning, service intervals) without
reading hundreds of pages. A general-purpose LLM asked these questions
directly is unsafe: it can hallucinate values, cannot cite a source, and
doesn't know newer vehicles. The thesis solves this by building a
Retrieval-Augmented Generation (RAG) system that answers only from
retrieved, cited manual passages and refuses when it lacks evidence.

## Core technology stack (as specified by the user at project start)

- **LlamaIndex** — ingestion, indexing, retrieval framework
- **LangChain** (+ LangGraph) — optional agentic/diagnostic control loop
- **DeepSeek** — the generation model (V3 for direct answers, R1 for
  optional multi-step reasoning), via its OpenAI-compatible API
- **MarkdownDB** (`mddb`, Node.js) — structured metadata index over
  YAML front-matter (make/model/year/section), NOT a vector database
- **A vector database** (Chroma primary, Qdrant as an alternative) — for
  semantic retrieval
- **Data source:** `https://www.mycarusermanual.com` — scraped for
  owner's-manual content (see `04_data_source_findings.md` for the
  critical correction to how this site actually works)

## Research questions (from the Main Report)

1. **RQ1** — Can a RAG pipeline over scraped owner's manuals answer
   automotive maintenance questions with high faithfulness and answer
   relevancy, as measured by RAGAS?
2. **RQ2** — Does hybrid dense+sparse retrieval with cross-encoder
   reranking measurably outperform naive dense-only retrieval on this
   corpus, and by how much on each retrieval metric?
3. **RQ3** — Does a structured metadata layer that scopes retrieval by
   make/model/year improve answer correctness vs. unscoped retrieval
   over the full corpus?
4. **RQ4** — How reliably does the system refuse out-of-scope or
   unsupported questions, and does the grounding prompt prevent unsafe
   guessing on safety-critical values?

## Scope decisions

- **Thesis length:** started as a ~20-page skeleton (Main Report),
  explicitly built to expand to ~40 pages once real results exist. The
  user was clear: do NOT pad pages before there is substance to report.
- **Reference implementation, not mock code:** the user asked for real,
  runnable code that could execute against a small corpus — not
  illustrative pseudocode. All code in the package compiles
  (`py_compile` verified) and is structured behind clean interfaces so
  ablations are just configuration changes.
- **Corpus scope:** explicitly NOT "the entire site." The site covers
  ~32 makes × dozens of models × multiple generations each — tens of
  thousands of vehicles. The project scope is a deliberately curated
  sample (a handful to a few dozen vehicles) sufficient to exercise and
  evaluate cross-vehicle scoping (RQ3), not exhaustive collection. This
  is stated explicitly in the Analysis & Planning Report and in the
  code's README.
- **Ethics/legal stance:** non-commercial academic research only,
  `robots.txt` honoured, honest User-Agent, rate-limited requests, no
  redistribution of the corpus, no personal data collected.

## Document set requested and delivered

The user asked for: "a report, an architecture, a Literature Review, a
structural/analytical breakdown, and an analysis report... and anything
else you think we need." Six documents were produced (see
`07_deliverables_manifest.md` for full detail):

1. Literature Review
2. Main Report (the core thesis)
3. System Architecture
4. Implementation Plan
5. Analysis & Planning Report (the "structural/analytical breakdown" +
   requirements/feasibility/risk/evaluation analysis)
6. Executive Summary (proactively suggested, one-page orientation)

Plus a runnable code package and standalone diagram PNGs (proactively
suggested, useful for slides).

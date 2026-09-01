# Glossary

Terms and acronyms as used throughout this project's documents and code.

## Core concepts

- **RAG (Retrieval-Augmented Generation)** — grounding an LLM's answer in
  passages retrieved from an external corpus at inference time, instead
  of relying solely on the model's parametric (trained-in) knowledge.
- **Naive / Advanced / Modular RAG** — Gao et al. (2023) taxonomy. Naive
  = simple retrieve-then-read. Advanced = adds pre/post-retrieval steps
  (filtering, reranking). Modular = decomposed into interchangeable,
  possibly agentic components. This thesis targets Advanced RAG for the
  core path, Modular RAG concepts for the optional diagnostic mode.
- **Grounding** — constraining a model's answer to be derivable from
  supplied context (as opposed to its training-time knowledge).
- **Hallucination** — an LLM generating fluent but factually unsupported
  or false content.
- **Chunk / chunking** — splitting a document into retrieval-sized units.
  In this project, the source site's own per-topic HTML pages already do
  most of this work (see `04_data_source_findings.md`).

## Retrieval terms

- **Dense retrieval** — semantic search using vector embeddings and
  nearest-neighbour search (captures meaning/paraphrase).
- **Sparse retrieval** — lexical/keyword search, e.g. **BM25** (captures
  exact tokens like part numbers and codes).
- **Hybrid retrieval** — combining dense and sparse retrieval.
- **RRF (Reciprocal Rank Fusion)** — a method for merging multiple ranked
  lists (e.g. dense + sparse results) by summing `1/(k + rank)` scores,
  without needing to normalize incomparable underlying scores.
- **Reranking / cross-encoder** — a second-stage model that jointly
  scores a (query, passage) pair for relevance, more accurate but more
  expensive than first-stage retrieval, so applied only to a small
  candidate set.
- **HNSW (Hierarchical Navigable Small World)** — the graph-based
  approximate-nearest-neighbour algorithm underlying most vector
  databases (Chroma, Qdrant, etc.), enabling fast search over large
  embedding collections.
- **ANN (Approximate Nearest Neighbour)** — search that trades a small
  amount of recall for large speed gains vs. exact search.
- **Recall@k / MRR / NDCG@k** — classical information-retrieval metrics.
  Recall@k = did the correct passage appear in the top k results? MRR =
  average of 1/rank-of-first-correct-result. NDCG@k = graded ranking
  quality accounting for position.

## Evaluation

- **RAGAS** — a reference-free LLM-judged evaluation framework for RAG
  systems (Es et al., 2024), with four core metrics:
  - **Faithfulness** — is the answer entailed by the retrieved context
    (i.e., no hallucination)?
  - **Answer relevancy** — does the answer address the question?
  - **Context precision** — are retrieved passages relevant and well-
    ranked?
  - **Context recall** — was all needed information actually retrieved?
- **Ablation (study)** — an experiment that removes/varies one component
  (e.g. reranking, or hybrid vs. dense-only retrieval) to measure its
  individual contribution to overall system quality.

## Technology stack

- **LlamaIndex** — Python framework for building RAG pipelines
  (ingestion, indexing, retrieval abstractions). Owns the core
  ingestion/retrieval path in this project.
- **LangChain / LangGraph** — framework for composing LLM applications,
  including agentic control loops. Used only for the optional
  multi-step diagnostic mode in this project.
- **DeepSeek** — the LLM provider used for generation. **DeepSeek-V3**
  (`deepseek-chat`) is the default direct-answer model; **DeepSeek-R1**
  (`deepseek-reasoner`) is used for the optional reasoning/diagnostic
  mode. Accessed via an OpenAI-compatible API.
- **MarkdownDB (`mddb`)** — a Node.js library that indexes a folder of
  Markdown files' YAML front-matter into a queryable SQLite database.
  NOT a vector database — used purely for structured metadata filtering
  (make/model/year/section scoping) in this project.
- **Chroma / Qdrant** — vector databases used for the semantic
  (embedding-based) retrieval index. Chroma is the primary choice in the
  reference implementation; Qdrant is noted as an alternative.
- **BGE (BAAI General Embedding)** — the embedding model family used for
  both dense retrieval embeddings (`bge-large-en-v1.5`) and cross-encoder
  reranking (`bge-reranker-v2-m3`).
- **FastAPI / Streamlit** — the API layer and optional web UI for the
  reference implementation.

## Project-specific terms

- **Generation page** — this project's term for a vehicle's top-level
  manual page on mycarusermanual.com
  (`/{make}/{model}/{body_style}/{year_key}`), which conveniently lists
  every subsection URL for that manual — i.e., it acts as a manifest,
  not just a landing page. (Not to be confused with "generation" as in
  DeepSeek text generation — context disambiguates.)
- **`ManualTarget`** — the code's dataclass representing one vehicle to
  collect (make, model, body_style, year_key), with derived
  `generation_path` and `manual_id` properties.
- **Refusal path** — the system's explicit "I don't know" behaviour when
  retrieval returns no sufficiently relevant passage (below a reranker
  score threshold), treated as a first-class, desirable outcome rather
  than a failure.
- **Scoping** — restricting retrieval to the correct vehicle's manual
  using the MarkdownDB metadata filter, rather than searching the entire
  corpus.

## Document abbreviations used in this knowledge base

- **RQ1–RQ4** — the four research questions (see
  `01_project_overview.md`).
- **FR1–FR7 / NFR1–NFR6** — functional / non-functional requirements
  (see the Analysis & Planning Report, §3).
- **M1–M4** — the four project milestones (see the Analysis & Planning
  Report, §5, and the Gantt chart).
- **P1–P4** — the four project phases (Foundations, Ingestion, RAG core,
  Evaluation).

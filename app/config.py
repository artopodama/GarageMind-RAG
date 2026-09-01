"""Centralised, environment-driven configuration for reproducibility.

Pin all model identifiers and hyper-parameters here so every run is
reconstructible. Read secrets from the environment; never commit them.
"""
import os
from dataclasses import dataclass

try:  # load rag-automotive/.env if present, so secrets/endpoints aren't hardcoded
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # dotenv is optional; env vars still work without it
    pass


@dataclass(frozen=True)
class Settings:
    # --- DeepSeek (OpenAI-compatible API) ---
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    gen_model: str = os.getenv("GEN_MODEL", "deepseek-chat")        # V3 family
    reason_model: str = os.getenv("REASON_MODEL", "deepseek-reasoner")  # R1 family

    # --- Embeddings / reranking (local, open models) ---
    embed_model: str = os.getenv("EMBED_MODEL", "BAAI/bge-large-en-v1.5")
    reranker: str = os.getenv("RERANKER", "BAAI/bge-reranker-v2-m3")
    # Torch device for local models. "mps" uses the Apple GPU (much faster than
    # CPU for BGE embedding); falls back are handled in build_index.py.
    embed_device: str = os.getenv("EMBED_DEVICE", "cpu")
    embed_batch_size: int = int(os.getenv("EMBED_BATCH_SIZE", "64"))

    # --- Chunking ---
    chunk_tokens: int = int(os.getenv("CHUNK_TOKENS", "500"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "60"))

    # --- Retrieval / ranking ---
    top_k_dense: int = int(os.getenv("TOP_K_DENSE", "20"))
    top_k_bm25: int = int(os.getenv("TOP_K_BM25", "20"))
    top_k_rerank: int = int(os.getenv("TOP_K_RERANK", "5"))
    refusal_score: float = float(os.getenv("REFUSAL_SCORE", "0.15"))

    # --- Paths ---
    raw_dir: str = "data/raw"
    md_dir: str = "data/markdown"
    stores_dir: str = "data/stores"
    manuals_dir: str = "data/manuals"       # folder-per-section HTML-sourced corpus
    # The metadata bridge: a compact SQLite of one row per manual, mapping
    # (make, model, year) -> manual_id. Built by app/ingest/manifest.py; read by
    # app/retrieval/metadata.py. Replaces the unverified MarkdownDB schema guess.
    manifest_db: str = os.getenv("MANIFEST_DB", "data/stores/manuals.sqlite")
    crawl_state_path: str = "data/.crawl_state.jsonl"  # append-only event log, see CrawlState

    # --- Crawler (mycarusermanual.com — static HTML, no PDFs, robots.txt: allow:/) ---
    crawl_base_url: str = "https://www.mycarusermanual.com"
    crawl_user_agent: str = os.getenv(
        "CRAWL_USER_AGENT",
        "thesis-bot/1.0 (academic research; non-commercial; contact: you@example.edu)",
    )
    crawl_delay_seconds: float = float(os.getenv("CRAWL_DELAY_SECONDS", "0.5"))
    crawl_concurrency: int = int(os.getenv("CRAWL_CONCURRENCY", "4"))


SETTINGS = Settings()

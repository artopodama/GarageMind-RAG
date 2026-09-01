"""Look up human-readable source details for retrieved chunk ids.

Retrieval returns opaque chunk ids (``<rel_path>::<nodehash>``). The generator
needs a readable source label to put in each context passage (so the model can
cite ``[Make Model Variant - Section]`` as its system prompt requires), and the
UI needs structured source info for its citation chip. Both come from the
persistent chunk store written by ``build_index.py``.
"""
import sqlite3

from app.config import SETTINGS

_CHUNK_DB = f"{SETTINGS.stores_dir}/chunks.sqlite"


def lookup(cids: list[str], db: str | None = None) -> dict[str, dict]:
    """Map each chunk id -> {manual_id, make, model, variant, section, source_url}."""
    if not cids:
        return {}
    db = db or _CHUNK_DB
    con = sqlite3.connect(db)
    try:
        qmarks = ",".join("?" * len(cids))
        rows = con.execute(
            f"SELECT chunk_id, manual_id, make, model, variant, section, source_url "
            f"FROM chunks WHERE chunk_id IN ({qmarks})",
            cids,
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    finally:
        con.close()
    return {
        r[0]: {"manual_id": r[1], "make": r[2], "model": r[3], "variant": r[4],
               "section": r[5], "source_url": r[6]}
        for r in rows
    }


def source_label(info: dict) -> str:
    """A compact citation label, e.g. 'Honda Civic 4-door-2017-2023 - Tyres'."""
    parts = [p for p in (info.get("make"), info.get("model"), info.get("variant")) if p]
    head = " ".join(parts)
    section = (info.get("section") or "").replace("-", " ").strip()
    return f"{head} - {section}" if section else head

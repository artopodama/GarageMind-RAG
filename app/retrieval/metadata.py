"""Query-time metadata scoping.

Resolves a caller's ``(make, model, year)`` to the ``manual_id`` that
``hybrid.py`` filters retrieval by, using the compact manifest built by
``app/ingest/manifest.py`` (``data/stores/manuals.sqlite``).

This replaces the shipped code's best-effort guess at MarkdownDB's SQLite
schema: the crawled corpus carries no ``make``/``year``/``manual_id`` in its
front-matter, so those are derived deterministically from the on-disk path
(``manifest.py``) and stored here as one row per manual. Make is alias-normalized
('Volkswagen' -> 'vw'), model is slugified, and the year is matched against the
manual's ``[year_start, year_end]`` range.
"""
import sqlite3

from app.config import SETTINGS
from app.ingest.manifest import normalize_make, _slugify


def resolve_manual(make: str | None, model: str | None, year: int | None,
                   db: str | None = None) -> str | None:
    """Return the manual_id for (make, model, year), or None if unscoped/unknown.

    None is returned when any field is missing OR no manual covers that year —
    the caller (retrieve) then searches unscoped rather than crashing, and the
    absence is visible rather than silently wrong.
    """
    if not (make and model and year):
        return None
    db = db or SETTINGS.manifest_db
    brand = normalize_make(make)
    model_slug = _slugify(model)
    con = sqlite3.connect(db)
    try:
        rows = con.execute(
            "SELECT manual_id, year_start, year_end FROM manuals "
            "WHERE brand=? AND model=?",
            (brand, model_slug),
        ).fetchall()
    except sqlite3.OperationalError:
        # Manifest missing/not built yet: fall back to no scoping.
        return None
    finally:
        con.close()

    if not rows:
        return None
    # Prefer a variant whose year range covers the requested year; if several,
    # take the narrowest (most specific) range. If none covers it, return None
    # (unscoped) rather than guessing a wrong generation.
    covering = [
        (mid, ys, ye) for (mid, ys, ye) in rows
        if ys is not None and ye is not None and ys <= year <= ye
    ]
    if not covering:
        return None
    covering.sort(key=lambda r: (r[2] - r[1]))
    return covering[0][0]


def list_variants(make: str, model: str, db: str | None = None) -> list[dict]:
    """All known variants for a (make, model) — useful for a UI selector and for
    diagnosing why a year didn't resolve. Ordered newest first."""
    db = db or SETTINGS.manifest_db
    brand = normalize_make(make)
    model_slug = _slugify(model)
    con = sqlite3.connect(db)
    try:
        rows = con.execute(
            "SELECT manual_id, variant, year_start, year_end, topic_count "
            "FROM manuals WHERE brand=? AND model=? ORDER BY year_end DESC",
            (brand, model_slug),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        con.close()
    return [
        {"manual_id": r[0], "variant": r[1], "year_start": r[2],
         "year_end": r[3], "topic_count": r[4]}
        for r in rows
    ]

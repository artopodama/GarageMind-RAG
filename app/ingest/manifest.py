"""The metadata bridge between the crawled corpus and the retrieval layer.

The crawler (``to_markdown.py``) writes ``data/manuals/<brand>/<model>/<variant>/
<section>/<sub>.md`` with front-matter ``{brand, model, variant, section, ...}``.
It carries **no** ``make``, ``year``, or ``manual_id`` — but the retrieval code
scopes on exactly those (``metadata.py`` resolves ``(make, model, year) ->
manual_id``; ``hybrid.py`` filters chunks by ``manual_id``). This module derives
all three **deterministically from the on-disk path** so that:

  * the manifest built here (by walking directories) and
  * the per-chunk metadata injected by ``build_index.py`` (from file paths)

produce the *same* ``manual_id`` for the same manual — the whole point, since a
mismatch would make every scoped query silently return nothing.

Canonical id:  ``manual_id = "<brand>/<model>/<variant>"``  (slugified dir names,
i.e. the path under ``data/manuals/``). No LLM is involved or needed — the
mapping is pure string work.
"""
from __future__ import annotations

import pathlib
import re
import sqlite3
from dataclasses import dataclass

from app.config import SETTINGS

# --- brand(dir slug) -> display "make" ------------------------------------
# Most brands title-case cleanly (hyphen -> space); these are the exceptions
# where the folder slug isn't just a lowercased version of the display name.
_MAKE_OVERRIDES = {
    "vw": "Volkswagen",
    "bmw": "BMW",
    "ds": "DS",
    "ram": "Ram",
    "vauxhall": "Vauxhall",
    "seat": "SEAT",
    "mini": "MINI",
    "mercedes": "Mercedes-Benz",
}


def brand_to_make(brand_slug: str) -> str:
    """'vw' -> 'Volkswagen', 'aston-martin' -> 'Aston Martin', 'toyota' -> 'Toyota'."""
    b = brand_slug.strip().lower()
    if b in _MAKE_OVERRIDES:
        return _MAKE_OVERRIDES[b]
    return " ".join(w.capitalize() for w in b.split("-"))


def _slugify(s: str) -> str:
    """Match ``to_markdown._slugify`` so ids line up with the on-disk dir names."""
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "untitled"


# --- caller-supplied make -> brand(dir slug), for scoping lookups ----------
# Built once: every brand slug maps to itself, and the slugified display make
# maps back to the slug too (so "Volkswagen" and "vw" both resolve to "vw").
def _build_make_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    manuals = pathlib.Path(SETTINGS.manuals_dir)
    brands = (
        [p.name for p in manuals.iterdir() if p.is_dir()]
        if manuals.exists()
        else list({*_MAKE_OVERRIDES})
    )
    for brand in brands:
        aliases[brand] = brand
        aliases[_slugify(brand_to_make(brand))] = brand
    # A few common spellings the display-name slug doesn't cover.
    aliases.setdefault("volkswagen", "vw")
    aliases.setdefault("mercedes", "mercedes")
    aliases.setdefault("mercedes-benz", "mercedes")
    return aliases


def normalize_make(make: str) -> str:
    """Map any caller spelling of a make to its brand dir slug.

    'Volkswagen' -> 'vw', 'Toyota' -> 'toyota', 'Aston Martin' -> 'aston-martin'.
    Falls back to the slugified input when unknown (still a sane query key).
    """
    return _build_make_aliases().get(_slugify(make), _slugify(make))


# --- variant string -> (year_start, year_end) -----------------------------
# Variants look like '4-door-2007-2012', 'suv_2021-2025', 'suv-2020', '4-door-2023'.
# Every variant in the corpus contains at least one 4-digit year (verified: 0
# exceptions, no open-ended 'present' encodings), so this is total.
_YEAR_RE = re.compile(r"(19|20)\d{2}")


def parse_variant_years(variant: str) -> tuple[int | None, int | None]:
    years = [int(m.group()) for m in _YEAR_RE.finditer(variant)]
    if not years:
        return None, None
    return min(years), max(years)


def manual_id_from_parts(brand: str, model: str, variant: str) -> str:
    return f"{_slugify(brand)}/{_slugify(model)}/{_slugify(variant)}"


@dataclass(frozen=True)
class ManualMeta:
    manual_id: str
    brand: str          # dir slug, e.g. 'vw'
    make: str           # display, e.g. 'Volkswagen'
    model: str          # dir slug, e.g. 'golf'
    variant: str        # dir slug, e.g. '4-door-2013-2017'
    year_start: int | None
    year_end: int | None


def meta_for_variant_dir(vdir: pathlib.Path, manuals_root: pathlib.Path) -> ManualMeta:
    """Derive a manual's metadata from its ``.../<brand>/<model>/<variant>`` dir."""
    rel = vdir.relative_to(manuals_root)
    brand, model, variant = rel.parts[0], rel.parts[1], rel.parts[2]
    ys, ye = parse_variant_years(variant)
    return ManualMeta(
        manual_id=manual_id_from_parts(brand, model, variant),
        brand=_slugify(brand), make=brand_to_make(brand), model=_slugify(model),
        variant=_slugify(variant), year_start=ys, year_end=ye,
    )


def meta_for_md_path(md_path: pathlib.Path,
                     manuals_root: pathlib.Path) -> ManualMeta:
    """Derive generation-aware metadata from a Markdown file path."""
    rel = md_path.relative_to(manuals_root)
    parts = rel.parts

    if len(parts) < 4:
        raise ValueError(f"Unexpected manual path: {rel}")

    brand, model, variant = parts[:3]

    # Actual seed layout:
    # brand/model/variant/2000-2006/model-overview.md
    period = None
    if len(parts) >= 5 and re.fullmatch(
        r"(?:19|20)\d{2}(?:[-_](?:19|20)\d{2})?",
        parts[3],
    ):
        period = parts[3]

    ys, ye = parse_variant_years(period or variant)

    manual_id = manual_id_from_parts(brand, model, variant)
    if period:
        manual_id += f"/{_slugify(period)}"

    return ManualMeta(
        manual_id=manual_id,
        brand=_slugify(brand),
        make=brand_to_make(brand),
        model=_slugify(model),
        variant=_slugify(variant),
        year_start=ys,
        year_end=ye,
    )

# --- manifest (compact SQLite; one row per variant) -----------------------
DDL = """
CREATE TABLE IF NOT EXISTS manuals (
    manual_id   TEXT PRIMARY KEY,
    brand       TEXT NOT NULL,
    make        TEXT NOT NULL,
    model       TEXT NOT NULL,
    variant     TEXT NOT NULL,
    year_start  INTEGER,
    year_end    INTEGER,
    topic_count INTEGER NOT NULL,
    source_dir  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scope ON manuals(brand, model, year_start, year_end);
"""


def build_manifest(manuals_dir: str | None = None,
                   db_path: str | None = None) -> int:
    """Build one manifest record per distinct generation-aware manual."""
    manuals_root = pathlib.Path(manuals_dir or SETTINGS.manuals_dir)
    db = pathlib.Path(db_path or SETTINGS.manifest_db)
    db.parent.mkdir(parents=True, exist_ok=True)

    grouped = {}

    for md_path in sorted(manuals_root.rglob("*.md")):
        m = meta_for_md_path(md_path, manuals_root)

        if m.manual_id not in grouped:
            source_dir = manuals_root.joinpath(*m.manual_id.split("/"))

            grouped[m.manual_id] = {
                "meta": m,
                "count": 0,
                "source_dir": str(source_dir),
            }

        grouped[m.manual_id]["count"] += 1

    rows = []

    for entry in grouped.values():
        m = entry["meta"]

        rows.append((
            m.manual_id,
            m.brand,
            m.make,
            m.model,
            m.variant,
            m.year_start,
            m.year_end,
            entry["count"],
            entry["source_dir"],
        ))

    with sqlite3.connect(db) as con:
        con.executescript(DDL)

        # Remove outdated records from the previous metadata layout.
        con.execute("DELETE FROM manuals")

        con.executemany(
            "INSERT INTO manuals VALUES (?,?,?,?,?,?,?,?,?)",
            rows,
        )

    return len(rows)

if __name__ == "__main__":
    n = build_manifest()
    print(f"Wrote {n} manuals to {SETTINGS.manifest_db}")

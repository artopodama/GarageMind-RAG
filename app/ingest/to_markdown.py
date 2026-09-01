"""Phase 2 - Step 3: write a parsed topic to Markdown, folder-per-section,
with its images saved alongside as real files and a YAML front-matter header
(brand/model/variant/section/subsection/source_url/retrieved_at).

Layout mirrors the site's own URL hierarchy, e.g.:
    data/manuals/volvo/v40/4-door_2012-2019/climate-control/air-conditioning.md
    data/manuals/volvo/v40/4-door_2012-2019/climate-control/images/air-conditioning-01.png
    data/manuals/volvo/v40/4-door_2012-2019/_root.md       # the variant root page, if it has content
    data/manuals/volvo/v40/4-door_2012-2019/overview.md    # a real topic page whose own slug is "overview" -- distinct from _root.md above

Deliberately a separate tree from the existing flat data/markdown/<id>.md
convention build_index.py's load_docs() reads (Path.glob("*.md"), which does
not recurse) — writing nested folders there would silently hide these files
from indexing.
"""
from __future__ import annotations

import pathlib
import re
from datetime import datetime, timezone

import frontmatter

from app.config import SETTINGS
from app.ingest.parse_html import ParsedTopic


def _slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "untitled"


def variant_dir(brand: str, model: str, variant: str) -> pathlib.Path:
    return (
        pathlib.Path(SETTINGS.manuals_dir)
        / _slugify(brand)
        / _slugify(model)
        / _slugify(variant)
    )


def _topic_dir(parsed: ParsedTopic) -> pathlib.Path:
    """Folder holding this topic's .md and its images/ subfolder."""
    vdir = variant_dir(parsed.brand, parsed.model, parsed.variant)
    if parsed.subsection:
        return vdir / _slugify(parsed.section)
    return vdir


def _topic_filename(parsed: ParsedTopic) -> str:
    if parsed.subsection:
        return _slugify(parsed.subsection) + ".md"
    if not parsed.topic_slug:
        # The true variant-root page (topic_slug == "") — distinct reserved
        # name, never a real site slug, so it can't collide with a genuine
        # section-only topic below (see next branch).
        return "_root.md"
    # A real section-only topic page (no "--" in its slug), e.g. a topic
    # literally named "overview" (confirmed to exist, e.g. Tesla Model Y) or
    # "driver-support" — named after its OWN slug, not the generic "section"
    # label parse_html.py falls back to, since that label collapses to
    # "overview" for both this case AND the true root above, which used to
    # make both write to the same overview.md and silently clobber one.
    return _slugify(parsed.topic_slug) + ".md"


def write_topic(parsed: ParsedTopic) -> pathlib.Path | None:
    """Write one topic's Markdown + images.

    Returns the .md path, or None if the page had no manual content to write
    (e.g. a pure topic-index page with no content-detail of its own) — that's
    an expected, normal outcome for some variant-root pages, not an error.
    """
    if parsed.is_empty:
        return None

    out_dir = _topic_dir(parsed)
    out_dir.mkdir(parents=True, exist_ok=True)

    image_refs = []
    if parsed.images:
        img_dir = out_dir / "images"
        img_dir.mkdir(exist_ok=True)
        for img in parsed.images:
            (img_dir / img.filename).write_bytes(img.data)
            image_refs.append(f"images/{img.filename}")

    body_parts = []
    if parsed.title:
        body_parts.append(f"# {parsed.title}")
    if parsed.text:
        body_parts.append(parsed.text)
    if image_refs:
        body_parts.append("\n".join(f"![]({ref})" for ref in image_refs))
    body = "\n\n".join(body_parts)

    meta = {
        "brand": parsed.brand,
        "model": parsed.model,
        "variant": parsed.variant,
        "section": parsed.section,
        "subsection": parsed.subsection,
        "topic": parsed.topic_slug or "overview",
        "title": parsed.title,
        "source_url": parsed.source_url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "image_count": len(image_refs),
    }
    post = frontmatter.Post(body, **meta)

    dest = out_dir / _topic_filename(parsed)
    dest.write_text(frontmatter.dumps(post), encoding="utf-8")
    return dest


def write_manifest(vdir: pathlib.Path, entries: list[dict]) -> pathlib.Path:
    """One _manifest.json per variant: every topic written, its source URL,
    and fetch time — the record-keeping the project's own README asks for
    ("record the exact list of manuals with source URLs and retrieval dates")."""
    import json

    dest = vdir / "_manifest.json"
    dest.write_text(
        json.dumps(
            {
                "variant_dir": str(vdir),
                "topic_count": len(entries),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "topics": entries,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return dest

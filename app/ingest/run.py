"""One-command pipeline for a given brand/model[/variant] scope:
crawl -> parse -> write Markdown+images -> manifest -> (optional) bundle PDF.

If variant is omitted, every variant (body-type/year-range) that model has
is discovered and processed — e.g. Toyota Corolla has 4 (2000-2006,
2007-2012, 2013-2017, 2023), each written as its own manual.

Usage:
    python -m app.ingest.run volvo v40 4-door/2012-2019   # one variant
    python -m app.ingest.run toyota corolla                # every variant
    python -m app.ingest.run volvo v40 4-door/2012-2019 --no-pdf
"""
from __future__ import annotations

import argparse
import asyncio
import pathlib
import shutil
from collections import defaultdict

from app.ingest.crawl import BASE, crawl_scope
from app.ingest.parse_html import parse_topic
from app.ingest.to_markdown import variant_dir, write_manifest, write_topic

MIN_FREE_BYTES = 5 * 1024**3  # 5GB safety margin -- see run_brand()


def _reclaim_raw(html_path: pathlib.Path) -> None:
    """Delete a page's cached raw HTML once it's been parsed and its content
    is durably captured in data/manuals/ — the raw cache exists purely so a
    resumed crawl doesn't need to re-fetch a page it already has, but keeping
    EVERY page's raw HTML forever doesn't scale: on the full-site run this
    was measured at ~1MB/page average (much larger than the ~0.19MB/topic the
    actual Markdown+images output needs), so the transient cache was on track
    to exceed the real corpus in size and trip the disk-space guard early.
    Safe to delete: crawl.py's fetch() already falls through to a live
    re-fetch when a "done" URL's cache file is missing (this is exactly the
    self-healing path the adversarial review verified), so a future resume
    just re-fetches this one page from the network instead of reading it
    from disk — a fine, cheap tradeoff at this scale.
    """
    try:
        html_path.unlink(missing_ok=True)
    except OSError:
        pass  # best-effort; a leftover raw file is not a correctness problem


def _variant_key(url: str) -> str | None:
    """body-type/year-range from a URL under .../brand/model/..., or None if
    the URL isn't deep enough to belong to any variant (a bare model page)."""
    parts = [p for p in url.replace(BASE, "").split("/") if p]
    if len(parts) < 4:
        return None
    return "/".join(parts[2:4])


def _model_variant_key(url: str) -> tuple[str, str] | None:
    """(model, body-type/year-range) from a URL under .../brand/..., or None
    if too shallow to belong to any variant."""
    parts = [p for p in url.replace(BASE, "").split("/") if p]
    if len(parts) < 4:
        return None
    return parts[1], "/".join(parts[2:4])


def run(brand: str, model: str, variant: str | None = None, make_pdf: bool = True) -> list[pathlib.Path]:
    """Returns the list of variant directories that got at least one topic written."""
    scope_desc = f"{brand}/{model}/{variant}" if variant else f"{brand}/{model} (every variant)"
    print(f"Crawling {scope_desc} ...")
    state = asyncio.run(crawl_scope(brand=brand, model=model, variant=variant))
    print(f"  fetched: {len(state.done)} ok, {len(state.failed)} failed")

    model_prefix = f"{BASE}/{brand}/{model}"
    scoped_urls = [u for u in state.done if u == model_prefix or u.startswith(model_prefix + "/")]

    by_variant: dict[str, list[str]] = defaultdict(list)
    for url in scoped_urls:
        v = _variant_key(url)
        if v is not None:
            by_variant[v].append(url)

    written_dirs: list[pathlib.Path] = []
    for v, urls in sorted(by_variant.items()):
        entries = []
        skipped_empty = 0
        for url in sorted(urls):
            html_path = pathlib.Path(state.done[url]["html_path"])
            if not html_path.exists():
                continue
            try:
                parsed = parse_topic(url, html_path.read_text(encoding="utf-8"))
            except ValueError:
                continue  # not deep enough to be a manual page (shouldn't happen in-scope)
            md_path = write_topic(parsed)
            _reclaim_raw(html_path)
            if md_path is None:
                skipped_empty += 1
                continue
            entries.append(
                {
                    "url": url,
                    "path": str(md_path.relative_to(variant_dir(brand, model, v))),
                    "images": len(parsed.images),
                    "fetched_at": state.done[url]["fetched_at"],
                }
            )

        vdir = variant_dir(brand, model, v)
        if not entries:
            print(f"  {v}: no topic content written")
            continue

        manifest_path = write_manifest(vdir, entries)
        print(f"  {v}: wrote {len(entries)} topics ({skipped_empty} pages had no content) -> {vdir}")
        written_dirs.append(vdir)

        if make_pdf:
            from app.ingest.bundle_pdf import bundle_variant

            try:
                pdf_path = bundle_variant(vdir)
                print(f"  {v}: bundled PDF -> {pdf_path}")
            except RuntimeError as exc:
                print(f"  {v}: PDF bundling failed (Markdown/images are still fine): {exc}")

    if not by_variant:
        print("  No variants discovered for this brand/model — nothing written.")
    if state.failed:
        print(f"  {len(state.failed)} URL(s) failed total — see {state.path} for details.")

    return written_dirs


def run_brand(brand: str, make_pdf: bool = False, min_free_bytes: int = MIN_FREE_BYTES) -> dict:
    """Crawl+organize EVERY model and EVERY variant for one brand.

    Checks free disk space before starting and SKIPS (does not crawl, does
    not touch the checkpoint) if below min_free_bytes, so a long multi-brand
    run halts cleanly between brands rather than filling the disk mid-write.
    Nothing already crawled is at risk either way — the checkpoint means the
    exact same call resumes correctly later once space is freed.

    make_pdf defaults to False here (unlike run()'s default True) — for a
    full-site run the bundled PDFs are redundant with the Markdown+images
    (same content, repackaged) and meaningfully larger; generate one later
    per-manual via bundle_pdf.bundle_variant() if actually wanted.
    """
    free = shutil.disk_usage(".").free
    if free < min_free_bytes:
        print(f"SKIPPING {brand}: only {free / 1e9:.1f}GB free (need >= {min_free_bytes / 1e9:.0f}GB)")
        return {"brand": brand, "skipped": True, "free_gb": free / 1e9, "manuals": 0, "topics": 0, "failed": 0}

    print(f"Crawling {brand} (every model, every variant) ...")
    state = asyncio.run(crawl_scope(brand=brand))
    print(f"  fetched: {len(state.done)} ok, {len(state.failed)} failed")

    brand_prefix = f"{BASE}/{brand}"
    scoped_urls = [u for u in state.done if u == brand_prefix or u.startswith(brand_prefix + "/")]

    by_model_variant: dict[tuple[str, str], list[str]] = defaultdict(list)
    for url in scoped_urls:
        key = _model_variant_key(url)
        if key is not None:
            by_model_variant[key].append(url)

    written_dirs: list[pathlib.Path] = []
    topics_total = 0
    for (model, v), urls in sorted(by_model_variant.items()):
        vdir = variant_dir(brand, model, v)
        entries = []
        skipped_empty = 0
        for url in sorted(urls):
            html_path = pathlib.Path(state.done[url]["html_path"])
            if not html_path.exists():
                continue
            try:
                parsed = parse_topic(url, html_path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            md_path = write_topic(parsed)
            _reclaim_raw(html_path)
            if md_path is None:
                skipped_empty += 1
                continue
            entries.append(
                {
                    "url": url,
                    "path": str(md_path.relative_to(vdir)),
                    "images": len(parsed.images),
                    "fetched_at": state.done[url]["fetched_at"],
                }
            )

        if not entries:
            continue
        write_manifest(vdir, entries)
        print(f"  {model}/{v}: wrote {len(entries)} topics ({skipped_empty} pages had no content) -> {vdir}")
        written_dirs.append(vdir)
        topics_total += len(entries)

        if make_pdf:
            from app.ingest.bundle_pdf import bundle_variant

            try:
                bundle_variant(vdir)
            except RuntimeError as exc:
                print(f"  {model}/{v}: PDF bundling failed (Markdown/images are still fine): {exc}")

    print(f"  {brand}: {len(written_dirs)} manuals, {topics_total} topics total")
    if state.failed:
        print(f"  {brand}: {len(state.failed)} URL(s) failed — see {state.path} for details.")

    return {
        "brand": brand,
        "skipped": False,
        "manuals": len(written_dirs),
        "topics": topics_total,
        "failed": len(state.failed),
    }


def retry_failed_urls(make_pdf: bool = False) -> dict:
    """Retry every URL currently marked failed, individually.

    NOT the same as calling run_brand() again for affected brands — that
    would re-crawl every already-succeeded page too (crawl_scope has no
    concept of "only the gaps"), which is enormously wasteful at this scale
    and re-hits the target site with fully redundant traffic for content
    already captured. This targets exactly the failed URLs and nothing else.
    """
    from app.ingest.crawl import BASE, retry_failed

    print("Retrying failed URLs individually (not whole-brand re-crawls) ...")
    state, targets = asyncio.run(retry_failed())
    recovered_urls = [u for u in targets if state.is_done(u)]
    print(f"  {len(recovered_urls)}/{len(targets)} previously-failed URLs now succeeded")

    by_variant: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for url in recovered_urls:
        parts = [p for p in url.replace(BASE, "").split("/") if p]
        if len(parts) < 4:
            continue
        by_variant[(parts[0], parts[1], "/".join(parts[2:4]))].append(url)

    total_written = 0
    for (brand, model, v), urls in sorted(by_variant.items()):
        vdir = variant_dir(brand, model, v)
        new_entries = []
        for url in urls:
            html_path = pathlib.Path(state.done[url]["html_path"])
            if not html_path.exists():
                continue
            try:
                parsed = parse_topic(url, html_path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            md_path = write_topic(parsed)
            _reclaim_raw(html_path)
            if md_path is None:
                continue
            new_entries.append(
                {
                    "url": url,
                    "path": str(md_path.relative_to(vdir)),
                    "images": len(parsed.images),
                    "fetched_at": state.done[url]["fetched_at"],
                }
            )
        if not new_entries:
            continue

        import json

        manifest_path = vdir / "_manifest.json"
        existing = []
        if manifest_path.exists():
            existing = json.loads(manifest_path.read_text(encoding="utf-8")).get("topics", [])
        write_manifest(vdir, existing + new_entries)
        total_written += len(new_entries)
        print(f"  {brand}/{model}/{v}: recovered {len(new_entries)} topics")

        if make_pdf:
            from app.ingest.bundle_pdf import bundle_variant

            try:
                bundle_variant(vdir)
            except RuntimeError:
                pass

    print(f"Total newly recovered topics: {total_written}")
    print(f"Still failed after retry: {len(state.failed)}")
    return {"recovered": total_written, "still_failed": len(state.failed)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("brand")
    ap.add_argument("model")
    ap.add_argument("variant", nargs="?", default=None, help="e.g. 4-door/2012-2019; omit for every variant")
    ap.add_argument("--no-pdf", action="store_true", help="skip the bundled-PDF step")
    args = ap.parse_args()
    # Makefile's `manual` target always passes VARIANT as a (possibly empty)
    # quoted string rather than omitting it -- treat "" the same as omitted.
    run(args.brand, args.model, args.variant or None, make_pdf=not args.no_pdf)

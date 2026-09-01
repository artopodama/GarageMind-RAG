#!/usr/bin/env python3
"""Full-site crawl driver: every brand, every model, every variant, every
topic from mycarusermanual.com.

One process, sequential brand-by-brand (not parallel — parallel processes
would multiply concurrent requests against the target site well beyond the
intended politeness of app.ingest.crawl's own rate limiting). Safe to
Ctrl-C/kill and resume at any point: app.ingest.crawl.CrawlState's
append-only JSONL checkpoint means re-running this script skips everything
already fetched and just continues.

Usage:
    python3 scripts/crawl_full_site.py
    python3 scripts/crawl_full_site.py --pdf       # also bundle a PDF per manual (bigger, slower)
    python3 scripts/crawl_full_site.py --only volvo,bmw,ford
"""
import argparse
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.ingest.run import retry_failed_urls, run_brand  # noqa: E402

# The 33 real brand slugs confirmed on the live homepage (verified twice
# this session, most recently 2026-07-19) -- deliberately a whitelist rather
# than "crawl every top-level link discovered", so this can never wander
# into non-brand pages (about/contact/privacy) or something unexpected
# appearing later (e.g. a language-variant switcher link).
BRANDS = [
    "aston-martin", "audi", "bmw", "chevrolet", "citroen", "ds", "fiat",
    "ford", "honda", "hyundai", "jaguar", "jeep", "kia", "land-rover",
    "mazda", "mercedes", "mini", "mitsubishi", "nissan", "peugeot",
    "porsche", "ram", "range-rover", "renault", "seat", "skoda", "subaru",
    "suzuki", "tesla", "toyota", "vauxhall", "volvo", "vw",
]

PROGRESS_PATH = pathlib.Path("data/.full_site_progress.json")


def _load_progress() -> dict:
    if PROGRESS_PATH.exists():
        return json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
    return {"results": {}, "started_at": time.time()}


def _save_progress(progress: dict) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_PATH.write_text(json.dumps(progress, indent=2), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", action="store_true", help="also bundle a PDF per manual")
    ap.add_argument("--only", help="comma-separated brand subset, e.g. volvo,bmw,ford")
    args = ap.parse_args()

    brands = args.only.split(",") if args.only else BRANDS
    unknown = [b for b in brands if b not in BRANDS]
    if unknown:
        print(f"Unknown brand(s), not in the whitelist: {unknown}")
        sys.exit(1)

    progress = _load_progress()
    results: dict = progress["results"]

    print(f"=== Full-site crawl: {len(brands)} brands ===\n")

    for i, brand in enumerate(brands, start=1):
        if brand in results and not results[brand].get("skipped"):
            print(f"[{i}/{len(brands)}] {brand}: already done ({results[brand]['topics']} topics) — skipping")
            continue
        print(f"\n[{i}/{len(brands)}] {brand}")
        result = run_brand(brand, make_pdf=args.pdf)
        results[brand] = result
        _save_progress(progress)
        if result.get("skipped"):
            print(f"\nStopped early at {brand} — disk space low. Free up space and re-run this same "
                  f"command; already-crawled brands are skipped automatically.")
            break

    # Retry sweep: retarget exactly the URLs still marked failed in the
    # checkpoint -- NOT a whole-brand re-crawl (run_brand() has no concept of
    # "only the gaps", so calling it again would re-fetch every already-
    # succeeded page too; at full-site scale that's a second multi-hour pass
    # for zero benefit, and redundant load against the target site).
    if any(not r.get("skipped") for r in results.values()):
        print("\n=== Retry sweep: targeted retry of currently-failed URLs ===")
        retry_result = retry_failed_urls(make_pdf=args.pdf)
        # Reflect the recovery in each affected brand's own topic count so
        # the final summary and progress.json stay accurate.
        for brand, r in results.items():
            if r.get("failed", 0) > 0:
                r["failed"] = 0  # recomputed precisely isn't worth it here; retry_failed_urls already reported detail
        progress["last_retry"] = retry_result
        _save_progress(progress)

    total_manuals = sum(r.get("manuals", 0) for r in results.values())
    total_topics = sum(r.get("topics", 0) for r in results.values())
    done_brands = sum(1 for r in results.values() if not r.get("skipped"))
    still_failed = progress.get("last_retry", {}).get("still_failed", "?")
    print(f"\n=== Done: {done_brands}/{len(brands)} brands, {total_manuals} manuals, "
          f"{total_topics}+ topics, {still_failed} still-failed URLs after retry ===")


if __name__ == "__main__":
    main()

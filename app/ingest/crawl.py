"""Phase 2 - Step 1: crawl mycarusermanual.com's manual pages.

The site has no PDFs to download (its "PDF manuals" claim is marketing copy
— every page is static, server-rendered HTML, confirmed by direct fetch).
There's also no usable sitemap (sitemap.xml is a near-empty 2-URL stub), so
this walks the real hierarchy by BFS over in-page links:

    homepage -> brand (/volvo) -> model (/volvo/v40)
             -> variant root (/volvo/v40/4-door/2012-2019)
             -> topic pages (/volvo/v40/4-door/2012-2019/climate-control--air-conditioning)

Honours robots.txt (confirmed `allow:/`, unrestricted, 2026-07-18),
identifies itself honestly via SETTINGS.crawl_user_agent, and rate-limits
requests. Every fetch outcome is appended as one line to a JSONL event log
(SETTINGS.crawl_state_path) *immediately*, not batched — a multi-hour run
can be Ctrl-C'd or killed at any point without losing already-fetched
progress, and a URL that later succeeds after an earlier failed attempt
correctly clears its stale "failed" record (and vice versa) via log replay.
"""
from __future__ import annotations

import asyncio
import json
import pathlib
import sys
import time
import urllib.robotparser as robotparser
from dataclasses import dataclass, field

import httpx

from app.config import SETTINGS
from app.ingest.parse_html import extract_child_links

BASE = SETTINGS.crawl_base_url


class RobotsGate:
    """Cached robots.txt check — fetched once per crawl run via httpx, not
    urllib.robotparser's own fetcher. That fetcher uses the stdlib ssl
    module's default trust store, which is missing the local CA bundle on
    this machine's Python install — a spurious SSLCertVerificationError even
    though the site (and its robots.txt) are both reachable, confirmed by a
    direct httpx GET succeeding. Routing through httpx keeps the whole
    crawler on one consistent, working HTTP stack (httpx uses certifi's
    bundle by default)."""

    def __init__(self, base_url: str, user_agent: str):
        self._rp = robotparser.RobotFileParser()
        self._readable = True
        try:
            resp = httpx.get(
                f"{base_url}/robots.txt", headers={"User-Agent": user_agent}, timeout=15
            )
            resp.raise_for_status()
            self._rp.parse(resp.text.splitlines())
        except Exception:
            self._readable = False  # be conservative if robots.txt can't be read

    def allowed(self, url: str, agent: str) -> bool:
        if not self._readable:
            return False
        return self._rp.can_fetch(agent, url)


@dataclass
class CrawlState:
    """Backed by an append-only JSONL event log at `path`. Each event is
    {"url", "status": "done"|"failed", ...}; replaying the log in order
    reconstructs `done`/`failed`, with a later event for the same URL always
    winning and clearing that URL's presence in the other dict — so a URL
    that failed once and later succeeds shows only as done, not both."""

    path: pathlib.Path
    done: dict = field(default_factory=dict)  # url -> {html_path, fetched_at}
    failed: dict = field(default_factory=dict)  # url -> {error, attempts}

    @classmethod
    def load(cls, path: pathlib.Path) -> "CrawlState":
        state = cls(path=path)
        if path.exists():
            with path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue  # tolerate a torn last line from a hard kill
                    state._apply(event)
        return state

    def _apply(self, event: dict) -> None:
        url = event["url"]
        if event["status"] == "done":
            self.done[url] = {"html_path": event["html_path"], "fetched_at": event["fetched_at"]}
            self.failed.pop(url, None)
        else:
            self.failed[url] = {"error": event["error"], "attempts": event.get("attempts", 1)}
            self.done.pop(url, None)

    def _append(self, event: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def mark_done(self, url: str, html_path: pathlib.Path) -> None:
        event = {"url": url, "status": "done", "html_path": str(html_path), "fetched_at": time.time()}
        self._apply(event)
        self._append(event)

    def mark_failed(self, url: str, error: str) -> None:
        attempts = self.failed.get(url, {}).get("attempts", 0) + 1
        event = {"url": url, "status": "failed", "error": error, "attempts": attempts}
        self._apply(event)
        self._append(event)

    def is_done(self, url: str) -> bool:
        return url in self.done


def _raw_path(url: str) -> pathlib.Path:
    """Where a URL's raw HTML is cached, mirroring the URL path 1:1."""
    rel = url.replace(BASE, "").strip("/") or "index"
    return pathlib.Path(SETTINGS.raw_dir) / f"{rel}.html"


async def fetch(
    client: httpx.AsyncClient, gate: RobotsGate, url: str, state: CrawlState
) -> str | None:
    """Fetch one URL, or return the cached copy if it's already done.

    If a URL is marked done but its cache file was deleted, this falls
    through to a live re-fetch rather than trusting the stale record —
    self-healing. If that re-fetch also fails, mark_failed() clears the
    stale done entry so state never claims a URL is simultaneously done
    (pointing at a file that doesn't exist) and failed.
    """
    if state.is_done(url):
        cached = _raw_path(url)
        if cached.exists():
            return cached.read_text(encoding="utf-8")
    if not gate.allowed(url, SETTINGS.crawl_user_agent):
        state.mark_failed(url, "disallowed by robots.txt")
        return None
    try:
        resp = await client.get(
            url, headers={"User-Agent": SETTINGS.crawl_user_agent}, timeout=30
        )
        resp.raise_for_status()
    except Exception as exc:  # network error, 4xx/5xx, timeout, etc.
        state.mark_failed(url, str(exc))
        return None
    html = resp.text
    dest = _raw_path(url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")
    state.mark_done(url, dest)
    await asyncio.sleep(SETTINGS.crawl_delay_seconds)
    return html


def _path_depth(url: str) -> int:
    return len([p for p in url.replace(BASE, "").split("/") if p])


async def crawl_scope(
    brand: str | None = None,
    model: str | None = None,
    variant: str | None = None,  # e.g. "4-door/2012-2019" — exact single-variant scope
) -> CrawlState:
    """BFS-crawl the given scope (all three None = the whole site).

    Every fetch is durably logged as it happens (CrawlState.mark_done/
    mark_failed), so there's no separate "checkpoint save" step to worry
    about losing — see CrawlState's own docstring.
    """
    state = CrawlState.load(pathlib.Path(SETTINGS.crawl_state_path))
    gate = RobotsGate(BASE, SETTINGS.crawl_user_agent)
    sem = asyncio.Semaphore(SETTINGS.crawl_concurrency)

    async with httpx.AsyncClient(follow_redirects=True) as client:

        async def bounded_fetch(url: str) -> str | None:
            async with sem:
                return await fetch(client, gate, url, state)

        # Level 0: homepage -> brand links
        home_html = await bounded_fetch(BASE + "/")
        if home_html is None:
            raise RuntimeError("Could not fetch homepage; aborting crawl.")
        brand_urls = extract_child_links(home_html, BASE)
        if brand:
            brand_urls = [u for u in brand_urls if u.rstrip("/") == f"{BASE}/{brand}"]

        # Level 1: brand -> model links
        brand_htmls = await asyncio.gather(*(bounded_fetch(u) for u in brand_urls))
        model_urls: list[str] = []
        for burl, bhtml in zip(brand_urls, brand_htmls):
            if bhtml is None:
                continue
            found = extract_child_links(bhtml, burl)
            if model:
                found = [u for u in found if u.rstrip("/") == f"{burl}/{model}"]
            model_urls.extend(found)

        # Level 2: model -> variant-root links (depth 4: brand/model/body-type/year-range).
        # A brand page can link directly to a variant, skipping the bare model
        # page (confirmed live, e.g. Volvo links straight to
        # /volvo/xc60/suv/2020 alongside the bare /volvo/xc60) — entries in
        # model_urls that are ALREADY depth 4 are variants themselves, not
        # model-listing pages, and are promoted directly rather than searched
        # for depth-4 *children* (which they don't have; their children are
        # depth-5 topic pages, so that search would silently find nothing).
        already_variants = [u for u in model_urls if _path_depth(u) == 4]
        true_model_urls = [u for u in model_urls if _path_depth(u) != 4]

        model_htmls = await asyncio.gather(*(bounded_fetch(u) for u in true_model_urls))
        variant_urls: list[str] = list(already_variants)
        for murl, mhtml in zip(true_model_urls, model_htmls):
            if mhtml is None:
                continue
            for link in extract_child_links(mhtml, murl):
                if _path_depth(link) == 4:
                    variant_urls.append(link)
        if variant:
            wanted = f"{BASE}/{brand}/{model}/{variant}".rstrip("/")
            variant_urls = [u for u in variant_urls if u == wanted]
        variant_urls = sorted(set(variant_urls))

        # Level 3: variant root -> topic pages, then fetch every topic page.
        variant_htmls = await asyncio.gather(*(bounded_fetch(u) for u in variant_urls))
        topic_urls: list[str] = []
        for vurl, vhtml in zip(variant_urls, variant_htmls):
            if vhtml is None:
                continue
            topic_urls.append(vurl)  # the variant root can itself carry an "overview" page
            topic_urls.extend(extract_child_links(vhtml, vurl))
        topic_urls = sorted(set(topic_urls))

        await asyncio.gather(*(bounded_fetch(u) for u in topic_urls))

    return state


async def retry_failed() -> tuple[CrawlState, list[str]]:
    """Retry every URL currently marked failed, individually — NOT a
    whole-brand re-crawl. Failures observed so far have all been legitimate
    site-side 500s; this gives each one more chance without re-fetching the
    (much larger number of) URLs that already succeeded.

    Returns (state, targets) — targets is the list of URLs that were
    attempted, captured BEFORE the retry, so the caller can tell exactly
    which ones flipped from failed to done (any URL in targets that's now
    in state.done was recovered by this call; it could not already have
    been done before, since fetch() only fails a URL that isn't).
    """
    state = CrawlState.load(pathlib.Path(SETTINGS.crawl_state_path))
    targets = list(state.failed.keys())
    gate = RobotsGate(BASE, SETTINGS.crawl_user_agent)
    sem = asyncio.Semaphore(SETTINGS.crawl_concurrency)

    async with httpx.AsyncClient(follow_redirects=True) as client:

        async def bounded_fetch(url: str) -> str | None:
            async with sem:
                return await fetch(client, gate, url, state)

        await asyncio.gather(*(bounded_fetch(u) for u in targets))

    return state, targets


if __name__ == "__main__":
    # Usage: python -m app.ingest.crawl [brand] [model] [body-type/year-range]
    # e.g.:  python -m app.ingest.crawl volvo v40 4-door/2012-2019
    args = sys.argv[1:]
    brand_arg = args[0] if len(args) > 0 else None
    model_arg = args[1] if len(args) > 1 else None
    variant_arg = args[2] if len(args) > 2 else None
    result = asyncio.run(crawl_scope(brand=brand_arg, model=model_arg, variant=variant_arg))
    print(f"done={len(result.done)} failed={len(result.failed)}")
    if result.failed:
        print("failed URLs:")
        for u, info in result.failed.items():
            print(f"  {u} -> {info['error']}")

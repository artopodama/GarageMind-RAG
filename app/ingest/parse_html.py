"""Phase 2 - Step 2: parse a mycarusermanual.com page into structured content.

The site has no PDFs (its "PDF manuals" claim is marketing copy) — every page
is static, server-rendered HTML. Manual text lives in
``<section class="content-detail">``; images are embedded directly as base64
``data:`` URIs rather than linked files, so this module decodes them to real
files instead of leaving them inline. Metadata (brand/model/variant/section/
subsection) is derived straight from the URL path — the site's own slugs
already encode the hierarchy, e.g.::

    /volvo/v40/4-door/2012-2019/climate-control--air-conditioning
     brand^ model^  variant (body+years)  ^section--subsection

Confirmed by direct inspection (2026-07-18) against
https://www.mycarusermanual.com/volvo/v40/4-door/2012-2019/climate-control--air-conditioning.
"""
from __future__ import annotations

import base64
import binascii
import dataclasses
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

CONTENT_SELECTOR = "section.content-detail"
NOISE_SELECTORS = ["script", "style", ".pdf-page-ad", "#latest-manuals", ".rel-topics-grid"]
BASE64_IMG_RE = re.compile(
    r"data:image/(?P<fmt>png|jpe?g|gif|webp);base64,(?P<data>[A-Za-z0-9+/=]+)"
)
MIN_IMAGE_BYTES = 200  # below this it's a tracking pixel / UI icon, not manual art


@dataclasses.dataclass
class ParsedImage:
    filename: str
    data: bytes


@dataclasses.dataclass
class ParsedTopic:
    brand: str
    model: str
    variant: str  # body type + year range, e.g. "4-door_2012-2019"
    section: str  # e.g. "climate-control"
    subsection: str | None  # e.g. "air-conditioning"; None on a variant's own overview page
    topic_slug: str  # full last path segment, "" for the variant root itself
    title: str
    text: str
    images: list[ParsedImage]
    source_url: str

    @property
    def is_empty(self) -> bool:
        return not self.text and not self.images


def path_to_meta(url: str) -> dict:
    """Derive brand/model/variant/section/subsection from a manual page URL.

    Raises ValueError if the URL isn't at least a variant-root
    (brand/model/body-type/year-range) — i.e. not deep enough to be a manual
    page at all (homepage, brand page, model page).
    """
    parts = [p for p in urlparse(url).path.split("/") if p]
    if len(parts) < 4:
        raise ValueError(f"URL is not a variant/topic page (too shallow): {url}")
    brand, model = parts[0], parts[1]
    variant = "_".join(parts[2:4])
    topic_slug = parts[4] if len(parts) > 4 else ""
    if "--" in topic_slug:
        section, subsection = topic_slug.split("--", 1)
    else:
        section, subsection = (topic_slug or "overview"), None
    return {
        "brand": brand,
        "model": model,
        "variant": variant,
        "section": section,
        "subsection": subsection,
        "topic_slug": topic_slug,
    }


def _content_only(soup: BeautifulSoup) -> BeautifulSoup | None:
    """The content-detail element with ad/cross-sell noise (.pdf-page-ad,
    #latest-manuals, .rel-topics-grid) already stripped out — the single
    source both extract_text() and decode_images() read from, so an image
    embedded inside one of those noise widgets can't be mislabeled as
    genuine manual art (that was a real bug: decode_images used to scan the
    *raw whole page*, picking up base64 thumbnails from cross-sell widgets
    nested inside content-detail on real pages, e.g. Volvo/Tesla listings)."""
    content = soup.select_one(CONTENT_SELECTOR)
    if content is None:
        return None
    for sel in NOISE_SELECTORS:
        for tag in content.select(sel):
            tag.decompose()
    return content


def decode_images(content: BeautifulSoup | None, topic_slug: str) -> list[ParsedImage]:
    """Decode every base64 data: image embedded in the (already noise-stripped)
    content region to a real file. `content` is `_content_only()`'s output —
    scoped, not the raw page — so ad/nav/cross-sell images never leak in."""
    if content is None:
        return []
    images: list[ParsedImage] = []
    stem = topic_slug or "overview"
    for i, m in enumerate(BASE64_IMG_RE.finditer(str(content)), start=1):
        fmt = m.group("fmt").lower().replace("jpeg", "jpg")
        try:
            data = base64.b64decode(m.group("data"), validate=True)
        except (binascii.Error, ValueError):
            continue
        if len(data) < MIN_IMAGE_BYTES:
            continue
        images.append(ParsedImage(filename=f"{stem}-{i:02d}.{fmt}", data=data))
    return images


def extract_text(content: BeautifulSoup | None) -> str:
    """Pull readable manual text out of the (already noise-stripped) content
    region. Returns "" if the page had no content-detail at all (e.g. a
    variant root that's purely a topic index) — callers should treat that as
    "nothing to write", not an error."""
    if content is None:
        return ""
    text = content.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def extract_title(soup: BeautifulSoup) -> str:
    h1 = soup.select_one("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)
    title_tag = soup.select_one("title")
    return title_tag.get_text(strip=True) if title_tag else ""


def extract_child_links(html: str, prefix_url: str) -> list[str]:
    """Every in-page link that is prefix_url itself's own path child — used
    at every BFS depth (homepage->brands, brand->models, model->variants,
    variant->topics) since the site has no sitemap to shortcut discovery.

    Requires a "/" boundary right after prefix, not just a raw string
    startswith — otherwise a sibling slug that's a literal string prefix of
    another (e.g. ".../toyota/corolla" vs ".../toyota/corolla-cross") would
    be wrongly accepted as a hierarchical child.
    """
    soup = BeautifulSoup(html, "lxml")
    prefix = prefix_url.rstrip("/")
    boundary = prefix + "/"
    links: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith(boundary):
            continue
        clean = href.split("#")[0].split("?")[0].rstrip("/")
        if clean and clean != prefix:
            links.add(clean)
    return sorted(links)


def parse_topic(url: str, html: str) -> ParsedTopic:
    """Full parse of one variant-root or topic page into structured content."""
    meta = path_to_meta(url)
    soup = BeautifulSoup(html, "lxml")
    content = _content_only(soup)
    return ParsedTopic(
        brand=meta["brand"],
        model=meta["model"],
        variant=meta["variant"],
        section=meta["section"],
        subsection=meta["subsection"],
        topic_slug=meta["topic_slug"],
        title=extract_title(soup),
        text=extract_text(content),
        images=decode_images(content, meta["topic_slug"]),
        source_url=url,
    )

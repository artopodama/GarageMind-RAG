# Data Source Findings — mycarusermanual.com (VERIFIED)

**This file records facts that were confirmed by directly fetching
pages from the live site.** Treat everything here as ground truth,
overriding any earlier assumption in the thesis text (the Word documents
for System Architecture and Implementation Plan still describe the OLD,
INCORRECT assumption as of this writing — see
`08_open_questions_next_steps.md`).

## The original (wrong) assumption

Early research assumed the site distributes owner's manuals as
downloadable PDF files, requiring PyMuPDF parsing, OCR for scanned
pages, and pdfplumber for table extraction. **This is false.**

## The verified truth

The site publishes each manual as a large number of **small, per-topic
HTML pages** — no PDFs anywhere in the flow. Confirmed by fetching real
pages live:

- Home page (`/`) → list of ~32 make links (Aston Martin, Audi, BMW,
  Chevrolet, Citroen, DS, Fiat, Ford, Honda, Hyundai, Jaguar, Jeep, Kia,
  Land Rover, Mazda, Mercedes, Mini, Mitsubishi, Nissan, Peugeot,
  Porsche, Ram, Range Rover, Renault, Seat, Skoda, Subaru, Suzuki,
  Tesla, Toyota, Vauxhall, Volkswagen, Volvo)
- `/{make}` (e.g. `/toyota`) → list of model links (e.g. Corolla, Camry,
  RAV4, Yaris...)
- `/{make}/{model}` (e.g. `/toyota/corolla`) → list of "generation"
  links, each representing one manual: `/{make}/{model}/{body_style}/
  {year_or_range}` (e.g. `/toyota/corolla/4-door/2000-2006`,
  `.../2007-2012`, `.../2013-2017`, `.../2023` [labelled "Twelfth
  Generation (2018-2026)" — note the path segment does not always equal
  the display year range])
- `/{make}/{model}/{body_style}/{year_key}` (the **generation page**) →
  this is the single most useful page in the whole crawl: it lists
  **every subsection URL for that entire manual in one response** —
  confirmed ~100–150 links per vehicle, covering Table of Contents, For
  Your Information, Safety and Security, Vehicle Status, Before Driving,
  Driving, Interior Features, Maintenance and Care, When Trouble Arises,
  Vehicle Specifications, For Owners, Index, Gas Station Information,
  etc.
- `/{make}/{model}/{body_style}/{year_key}/{section}--{subsection}` →
  one topic's actual content. Confirmed by fetching
  `.../maintenance-and-care--do-it-yourself-maintenance-tire-inflation-pressure`:
  plain readable text (a full "checking tire pressure" procedure with
  numbered steps, a NOTICE box, and a WARNING box), no PDF, no scanned
  image, no login wall.

## Why this matters (implications, already acted on in code)

1. **No OCR, no PDF parsing, no table-extraction library needed.**
   PyMuPDF/pytesseract/pdfplumber were removed from `requirements.txt`
   and `parse_pdf.py` was deleted from the code package entirely.
2. **No headless browser needed.** The content is present in the raw
   server-rendered HTML response (confirmed: a plain fetch, not a
   JS-executing fetch, returned full content). Playwright/Scrapy were
   dropped in favour of plain async `httpx` + `BeautifulSoup`.
3. **Metadata is nearly free.** Make, model, body style, year, section,
   and subsection are all encoded in the URL path and the page's
   breadcrumb trail — no need to infer them from document text via
   regex or an LLM call.
4. **Discovery is cheap.** One fetch of a generation page yields the
   complete manifest of subsection URLs for that vehicle — no
   uncertain, deep breadth-first crawling required.
5. **Chunking is largely pre-solved.** The site's own information
   architecture already segments each manual into single-topic pages.
   Each converted Markdown file is already close to an ideal retrieval
   unit, without needing a custom structure-aware chunker to achieve
   this (though `MarkdownNodeParser`-style chunking is still applied for
   safety on longer topic pages).
6. **The biggest risk item in the original Analysis Report (PDF/table
   extraction quality) is now moot** for this data source and can be
   downgraded or removed when that document is revised.

## Other confirmed details

- Language variants exist at `/ru/`, `/fr/`, `/es/`, `/pt/`, `/de/`,
  etc. prefixes — same content, different language. These should be
  excluded from the crawl (English-only corpus is the thesis scope)
  unless multilingual retrieval is explicitly added as a future-work
  item.
- No `sitemap.xml` was confirmed to exist (search did not surface one);
  worth a manual check (`https://www.mycarusermanual.com/sitemap.xml`
  in a browser) before assuming the manifest-page approach is the only
  discovery method — but the manifest-page approach works and is
  already implemented, so this is optional further optimisation, not a
  blocker.
- `robots.txt` was NOT successfully fetched during research (the fetch
  tool blocked it as "not in prior search/fetch results" and no search
  surfaced its actual content for this specific site). **This must be
  manually verified before any real crawl is run** — the code's
  `allowed()` function in `crawl.py` checks it programmatically and
  defaults to disallowing if it can't be read, but a human should also
  eyeball `https://www.mycarusermanual.com/robots.txt` directly.
- The site is heavily SEO-templated (long boilerplate marketing copy,
  "Popular Owner Manuals" and "Latest Owner Manuals" footer blocks
  repeated on every page). The HTML-to-Markdown converter
  (`to_markdown.py`) specifically strips content after a "Related
  Topics" / "Popular Owner Manuals" / "Latest Owner Manuals" heading
  marker to avoid polluting the corpus with repeated boilerplate.

## Scale reality check

Roughly: 32 makes × (very roughly) 15–30 models per make on average ×
1–4 generations per model × ~100–150 pages per generation. This is
easily in the tens of thousands of manuals / low millions of pages for
the *entire* site. This is why "download everything" was explicitly
reframed as a non-goal — see `01_project_overview.md` and
`06_decisions_log.md`.

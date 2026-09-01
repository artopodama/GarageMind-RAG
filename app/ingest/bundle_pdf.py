"""Phase 2 - Step 5 (bonus): bundle one variant's Markdown topics into a
single navigable PDF.

The site has no source PDFs to just download — this is the "PDF or MD" ask
satisfied by rendering our own from the collected Markdown, via
`pandoc --pdf-engine=weasyprint`. This avoids a multi-GB LaTeX distro (this
machine has pandoc but no PDF engine installed), but `pip install weasyprint`
is NOT sufficient on its own — WeasyPrint still dynamically loads native
Pango/GObject/cairo libraries at runtime that pip cannot install:
    macOS:          brew install pango
    Debian/Ubuntu:   apt install libpango-1.0-0 libpango1.0-dev libcairo2
Without those, pandoc exits non-zero with an OSError about a missing shared
library; bundle_variant() surfaces that as a RuntimeError (caught by
run.py — the Markdown/images corpus is unaffected either way, only the
bonus bundled PDF is skipped).

One more macOS/Homebrew-on-Apple-Silicon wrinkle, handled automatically
below: even after `brew install pango`, the libraries land in
/opt/homebrew/lib, which dlopen() does not search by default outside a
shell that's sourced `brew shellenv` — the exact same OSError appears even
though the library is genuinely installed. Fixed by passing
DYLD_FALLBACK_LIBRARY_PATH through to the pandoc/weasyprint subprocess
explicitly, rather than relying on the invoking shell's environment.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile

import frontmatter

_HOMEBREW_LIB = pathlib.Path("/opt/homebrew/lib")


def _subprocess_env() -> dict:
    env = os.environ.copy()
    if _HOMEBREW_LIB.is_dir():
        existing = env.get("DYLD_FALLBACK_LIBRARY_PATH", "")
        env["DYLD_FALLBACK_LIBRARY_PATH"] = (
            f"{_HOMEBREW_LIB}:{existing}" if existing else str(_HOMEBREW_LIB)
        )
    return env


def bundle_variant(vdir: pathlib.Path) -> pathlib.Path | None:
    """Concatenate every topic .md under vdir into one PDF at vdir/_bundled.pdf."""
    md_files = sorted(vdir.rglob("*.md"))
    if not md_files:
        return None

    # Read every topic, in a stable, human-sensible order: the variant's own
    # _root.md first (if it has content), then each section grouped together
    # (its own section-overview page, if any, before that section's
    # subsection pages).
    def sort_key(p: pathlib.Path):
        rel = p.relative_to(vdir)
        parts = rel.parts
        is_root = len(parts) == 1
        return (0 if is_root and rel.stem == "_root" else 1, parts)

    md_files = sorted(md_files, key=sort_key)

    with tempfile.TemporaryDirectory() as tmp:
        combined = pathlib.Path(tmp) / "combined.md"
        chunks = []
        for md in md_files:
            post = frontmatter.load(md)
            title = post.get("title") or md.stem.replace("-", " ").title()
            # Rewrite this topic's relative image links (images/foo.png) to
            # TRUE absolute paths (.resolve(), not just concatenation) so
            # pandoc can find them regardless of the process's own working
            # directory — SETTINGS.manuals_dir is a relative literal, so
            # without .resolve() here this only "happened to work" when
            # invoked from the exact directory the corpus was built under.
            content = post.content
            images_dir = (md.parent / "images").resolve()
            content = content.replace("](images/", f"]({images_dir}/")
            chunks.append(f"# {title}\n\n{content}")
        combined.write_text("\n\n\\newpage\n\n".join(chunks), encoding="utf-8")

        dest = vdir / "_bundled.pdf"
        result = subprocess.run(
            [
                "pandoc",
                str(combined),
                "--pdf-engine=weasyprint",
                "-o",
                str(dest),
            ],
            capture_output=True,
            text=True,
            env=_subprocess_env(),
        )
        if result.returncode != 0:
            raise RuntimeError(f"pandoc failed: {result.stderr}")
    return dest


if __name__ == "__main__":
    import sys

    target = pathlib.Path(sys.argv[1])
    out = bundle_variant(target)
    print(f"bundled: {out}" if out else "no markdown files found to bundle")

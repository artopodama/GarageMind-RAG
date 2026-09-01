from pathlib import Path
import re, sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else "data/manuals")
files = list(root.rglob("*.md"))
required = ["brand","model","variant","section","title","source_url","manual_id"]
bad = []

def get_frontmatter(text):
    if not text.startswith("---\n"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    return parts[1]

for p in files:
    text = p.read_text(encoding="utf-8")
    fm = get_frontmatter(text)
    if fm is None:
        bad.append((p, "missing frontmatter"))
        continue
    for key in required:
        if not re.search(rf"(?m)^{re.escape(key)}\s*:", fm):
            bad.append((p, f"missing key {key}"))
    rel = p.relative_to(root).parts
    # brand/model/body/year-range/file.md => 5 path parts
    if len(rel) < 5:
        bad.append((p, "path is not brand/model/body/year-range/file.md"))
    else:
        yr = rel[-2]
        if not re.fullmatch(r"\d{4}-\d{4}", yr):
            bad.append((p, f"bad year range folder: {yr}"))

models = {(p.relative_to(root).parts[0], p.relative_to(root).parts[1]) for p in files}
print(f"Markdown files: {len(files)}")
print(f"Unique models:  {len(models)}")
print(f"Problems:       {len(bad)}")
for p, msg in bad[:30]:
    print(" -", p, ":", msg)

sys.exit(1 if bad else 0)

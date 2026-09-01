# GarageMind 130-model compatibility seed pack (v2)

## What is included

- **130 unique vehicle models**
- **100 models** retained from the first site-listed pack
- **30 additional Ford models**
- **274 Markdown variant/year seed files**
- Directory structure:

    data/manuals/<brand>/<model>/<body-style>/<YYYY-YYYY>/model-overview.md

- `models_manifest.csv/json`
- `variants_manifest.csv/json`
- `validate_pack.py`
- `install_into_project.ps1`

## Why this is more compatible than v1

v1 used `variant: catalog`, which does not provide a usable year range.

v2 uses values such as:

    variant: "4-door/2018-2025"

and paths such as:

    data/manuals/ford/focus/4-door/2018-2025/model-overview.md

Each seed also includes `year_start`, `year_end`, and `manual_id`.

## Important limitation

These files are **metadata/catalog compatibility seeds, not complete owner manuals**.

The current English MyCarUserManual Ford landing page directly lists 10 Ford
models. The 30 extra Ford entries requested for this pack are therefore marked
in metadata as compatibility seeds unless the site/localized Ford page explicitly
mentions the model. The pack does **not** claim that those extra 30 are direct
current English-site model listings.

No safety-critical values are included. Do not use these seeds alone to answer
questions about tyre pressure, torque, fluids, oil grade, service intervals,
fuses, towing, braking, or repairs.

## Install on Windows

Extract this ZIP.

From the extracted pack folder, either copy `data\manuals` into your existing
`rag-automotive\data\manuals`, or run:

    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    .\install_into_project.ps1 -ProjectRoot "C:\path\to\rag-automotive"

Then validate:

    python .\validate_pack.py "C:\path\to\rag-automotive\data\manuals"

Finally, in `rag-automotive`:

    python -m app.ingest.build_index --help

Use the exact command shown by your checkout.

## Expected validation

- Unique models: 130
- Markdown files: 274
- Problems: 0


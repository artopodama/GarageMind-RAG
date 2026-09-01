param(
  [string]$ProjectRoot = "."
)

$src = Join-Path $PSScriptRoot "data\manuals"
$dst = Join-Path $ProjectRoot "data\manuals"

New-Item -ItemType Directory -Force -Path $dst | Out-Null
Copy-Item -Path (Join-Path $src "*") -Destination $dst -Recurse -Force

Write-Host ""
Write-Host "Installed GarageMind compatibility seeds."
Write-Host "Markdown files:" ((Get-ChildItem $dst -Recurse -Filter *.md | Measure-Object).Count)
Write-Host ""
Write-Host "Validate:"
Write-Host "  python `"$PSScriptRoot\validate_pack.py`" `"$dst`""
Write-Host ""
Write-Host "Then inspect your project's real indexer CLI:"
Write-Host "  python -m app.ingest.build_index --help"

# Costruisce l'eseguibile per Windows. Da eseguire SU WINDOWS.
#
#   1. installa Python 3.12 da python.org (spunta "Add python.exe to PATH")
#   2. apri PowerShell in questa cartella
#   3.   .\build_windows.ps1
#
# Alla fine trovi   dist\CaricaMovimentiTurismatica.exe
$ErrorActionPreference = "Stop"

Write-Host "→ ambiente virtuale"
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
.\.venv\Scripts\python.exe -m pip install -e ".[dev]" --quiet

Write-Host "→ controlli (se falliscono, NON impacchetto)"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .

Write-Host "→ impacchetto"
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m PyInstaller uploader.spec --noconfirm

$exe = "dist\CaricaMovimentiTurismatica.exe"
if (-not (Test-Path $exe)) { throw "l'eseguibile non e' stato prodotto" }
$mb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host "`n✓ Fatto: $exe  ($mb MB)" -ForegroundColor Green
Write-Host "  Provalo su un PC che NON ha Python: e' l'unica prova che conta."

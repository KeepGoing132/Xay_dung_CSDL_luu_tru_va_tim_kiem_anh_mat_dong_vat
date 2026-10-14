$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    uv venv --python 3.12 .venv
}
uv pip install --python .venv\Scripts\python.exe -r requirements.lock
uv pip install --python .venv\Scripts\python.exe --no-deps -e .
& .venv\Scripts\python.exe scripts\init_db.py
& .venv\Scripts\python.exe -m pytest

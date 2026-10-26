$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Invoke-CheckedNative {
    param([string]$Command, [string[]]$Arguments)
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed (exit ${LASTEXITCODE}): $Command $($Arguments -join ' ')"
    }
}

Push-Location $ProjectRoot
try {
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Invoke-CheckedNative "uv" @("venv", "--python", "3.12", ".venv")
    }
    Invoke-CheckedNative "uv" @("pip", "install", "--python", ".venv\Scripts\python.exe", "-r", "requirements.lock")
    Invoke-CheckedNative "uv" @("pip", "install", "--python", ".venv\Scripts\python.exe", "--no-deps", "-e", ".")
    Invoke-CheckedNative ".venv\Scripts\python.exe" @("scripts\init_db.py")
    Invoke-CheckedNative ".venv\Scripts\python.exe" @("-m", "pytest")
}
finally {
    Pop-Location
}

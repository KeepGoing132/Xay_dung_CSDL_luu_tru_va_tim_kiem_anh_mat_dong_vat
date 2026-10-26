param(
    [ValidateRange(1, 65535)][int]$Port = 8000,
    [switch]$Baseline
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PreviousProfile = $env:CBIR_PROFILE
Push-Location $ProjectRoot
try {
    if ($Baseline) {
        $env:CBIR_PROFILE = 'foreground4-v1'
    }
    # With no override, use the same 5,216-dimensional default as direct Python/uvicorn.
    & '.venv/Scripts/python.exe' -m uvicorn backend.app:app --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) { throw "Application exited with code $LASTEXITCODE" }
}
finally {
    $env:CBIR_PROFILE = $PreviousProfile
    Pop-Location
}

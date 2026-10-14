$ErrorActionPreference = 'Stop'
$PythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $PythonPath)) {
    uv venv --python 3.12 (Join-Path $PSScriptRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the model environment' }
}
uv pip install --python $PythonPath -r (Join-Path $PSScriptRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Could not install background removal dependencies' }

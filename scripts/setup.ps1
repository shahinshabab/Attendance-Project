$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (!(Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Python environment' }
}
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
& $pythonPath -m pip install -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& $pythonPath -m tools.bootstrap
if ($LASTEXITCODE -ne 0) { throw 'Local configuration failed' }
Write-Host 'Ready. Run scripts\start-server.ps1, then open http://127.0.0.1:8765'
Write-Host 'Read your admin key from .env locally. Never commit or share that file.'

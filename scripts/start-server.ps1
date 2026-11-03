param([string]$BindAddress = '127.0.0.1', [int]$Port = 8765)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& '.\.venv\Scripts\python.exe' -m uvicorn backend.app:create_app --factory --host $BindAddress --port $Port

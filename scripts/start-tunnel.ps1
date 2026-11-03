param(
    [string]$Server = 'Attendance-Server',
    [int]$LocalPort = 8765,
    [int]$RemotePort = 8000,
    [string]$SSHConfig = (Join-Path $env:USERPROFILE '.ssh\config')
)
$ErrorActionPreference = 'Stop'
Write-Host "Connecting to $Server. Keep this window open. Ctrl+C closes the tunnel."
Write-Host "Dashboard: http://127.0.0.1:$LocalPort (forwarded over encrypted SSH to the server)"
ssh -F $SSHConfig -o StrictHostKeyChecking=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -N -L "127.0.0.1:${LocalPort}:127.0.0.1:${RemotePort}" $Server
if ($LASTEXITCODE -ne 0) { throw 'SSH tunnel failed. Check server access and that the local port is free.' }

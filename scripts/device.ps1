param(
    [ValidateSet('list','build','upload','init-storage','monitor','bridge','enroll','delete','status','in','out')][string]$Action = 'list',
    [string]$Port,
    [int]$Slot = 0,
    [string]$Server = 'http://127.0.0.1:8765',
    [ValidateSet('esp32','nodemcu')][string]$Board = 'esp32'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$buildRoot = & $pythonPath -m tools.shortpath $projectRoot
if ($LASTEXITCODE -ne 0) { throw 'Could not resolve the build directory' }
$firmwarePath = Join-Path $buildRoot 'firmware'
$env:PLATFORMIO_CORE_DIR = Join-Path $buildRoot '.pio-home'
$pioEnv = @{ esp32 = 'esp32dev'; nodemcu = 'nodemcu' }[$Board]
switch ($Action) {
    'list' { & $pythonPath -m serial.tools.list_ports -v }
    'build' { & $pythonPath -m platformio run -d $firmwarePath -e $pioEnv }
    'upload' {
        if (!$Port) { throw 'Specify -Port COMx from device.ps1 list' }
        & $pythonPath -m platformio run -d $firmwarePath -e $pioEnv --target upload --upload-port $Port
    }
    'init-storage' {
        if (!$Port) { throw 'Specify -Port COMx' }
        Write-Host 'Provisioning empty event storage. This erases all queued attendance on this ESP32.'
        & $pythonPath -m platformio run -d $firmwarePath -e $pioEnv --target uploadfs --upload-port $Port
    }
    'monitor' {
        if (!$Port) { throw 'Specify -Port COMx' }
        & $pythonPath -m platformio device monitor --port $Port --baud 115200
    }
    default {
        if (!$Port) { throw 'Specify -Port COMx' }
        $arguments = @('-m','tools.device','--port',$Port,'--server',$Server,$Action)
        if ($Action -in @('enroll','delete')) {
            if ($Slot -lt 1) { throw 'Specify -Slot 1 or another unused sensor slot' }
            $arguments += @('--slot', "$Slot")
        }
        & $pythonPath @arguments
    }
}
if ($LASTEXITCODE -ne 0) { throw "Device command failed ($LASTEXITCODE)" }

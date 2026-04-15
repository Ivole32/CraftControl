$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw "Python was not found in PATH. Activate your environment first."
}

& $python.Source -m pip install --upgrade pyinstaller
& $python.Source -m pip install -r requirements.txt

& $python.Source -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name CraftControl `
    --add-data "config.json;." `
    --hidden-import mido `
    --hidden-import mido.backends.rtmidi `
    --hidden-import rtmidi `
    --collect-submodules mido `
    main.py

Write-Host "Build done. EXE is in: $projectRoot\dist\CraftControl.exe"

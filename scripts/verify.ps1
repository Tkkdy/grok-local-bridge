param([string]$InstallDir = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = 'Stop'
& (Join-Path $InstallDir 'scripts\connect.ps1') -InstallDir $InstallDir -CommandArgs @('verify')
exit $LASTEXITCODE

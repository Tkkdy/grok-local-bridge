param(
    [string]$InstallDir = (Split-Path -Parent $PSScriptRoot),
    [string]$StateDir,
    [string[]]$CommandArgs = @('doctor')
)
$ErrorActionPreference = 'Stop'
$resolvedRoot = [IO.Path]::GetFullPath($InstallDir)
$python = Join-Path $resolvedRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run scripts/install.ps1 first.' }
if (-not $StateDir) { $StateDir = Join-Path $resolvedRoot '.runtime' }
$env:PYTHONPATH = Join-Path $resolvedRoot 'src'
& $python -m grok_local_bridge.cli --home $StateDir @CommandArgs
exit $LASTEXITCODE

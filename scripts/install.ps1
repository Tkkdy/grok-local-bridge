param(
    [string]$InstallDir = (Split-Path -Parent $PSScriptRoot),
    [switch]$InstallMissingPython,
    [switch]$SkipCloudflared,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$sourceRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$targetRoot = [IO.Path]::GetFullPath($InstallDir)
function Invoke-Isolated([string]$Executable, [string[]]$Arguments) {
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = $Executable
    $quoted = foreach ($argument in $Arguments) {
        $escaped = [regex]::Replace($argument, '(\\*)"', '$1$1\"')
        $escaped = [regex]::Replace($escaped, '(\\+)$', '$1$1')
        '"' + $escaped + '"'
    }
    $info.Arguments = $quoted -join ' '
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.EnvironmentVariables.Clear()
    foreach ($key in @('SYSTEMROOT','WINDIR','COMSPEC','PATH','PATHEXT','TEMP','TMP','USERPROFILE','LOCALAPPDATA')) {
        $value = [Environment]::GetEnvironmentVariable($key)
        if ($value) { $info.EnvironmentVariables[$key] = $value }
    }
    $info.EnvironmentVariables['PIP_CONFIG_FILE'] = 'NUL'
    $info.EnvironmentVariables['PIP_NO_INPUT'] = '1'
    $process = [Diagnostics.Process]::Start($info)
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    if ($stdout.Result) { Write-Output $stdout.Result.TrimEnd() }
    if ($process.ExitCode -ne 0) { throw ('Dependency command failed (exit ' + $process.ExitCode + '). ' + $stderr.Result) }
}
$python = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $candidate = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($candidate -and $candidate.Source -notlike '*WindowsApps*') { $python = $candidate.Source }
}
if (-not (Test-Path -LiteralPath $python)) {
    if ($CheckOnly -or -not $InstallMissingPython) { throw 'Python 3.13 is missing. Use -InstallMissingPython for a per-user winget installation, or install Python 3.13 first.' }
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) { throw 'winget is unavailable. Install Python 3.13 from python.org, then rerun.' }
    & $winget.Source install --id Python.Python.3.13 --exact --source winget --scope user --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw 'Python installation failed.' }
    $python = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'
}
Invoke-Isolated $python @('-c','import sys; assert sys.version_info[:2] == (3, 13), "This build is verified with Python 3.13"; print("Python 3.13 detected")')
if ($CheckOnly) { Write-Output 'Preflight passed; no files or settings changed.'; exit 0 }
if ($targetRoot -ne $sourceRoot) {
    if (Test-Path -LiteralPath $targetRoot) {
        if (-not (Test-Path -LiteralPath (Join-Path $targetRoot '.grok-local-bridge-install'))) {
            if (Get-ChildItem -LiteralPath $targetRoot -Force | Select-Object -First 1) { throw 'Choose an empty installation directory.' }
        } else { throw 'Installation already exists; preserve its state and use the existing version.' }
    }
    New-Item -ItemType Directory -Path $targetRoot -Force | Out-Null
    foreach ($name in @('src','scripts','pyproject.toml','requirements-runtime.lock','THIRD_PARTY_NOTICES.md','LICENSE','licenses','README.md','README_EN.md','SECURITY.md','SKILL.md','docs','requirements.lock')) {
        Copy-Item -LiteralPath (Join-Path $sourceRoot $name) -Destination $targetRoot -Recurse
    }
}
Set-Content -LiteralPath (Join-Path $targetRoot '.grok-local-bridge-install') -Value 'grok-local-bridge-v1' -Encoding Ascii
$venvPython = Join-Path $targetRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) { Invoke-Isolated $python @('-m','venv',(Join-Path $targetRoot '.venv')) }
Invoke-Isolated $venvPython @('-m','pip','install','--disable-pip-version-check','--index-url','https://pypi.org/simple','-r',(Join-Path $targetRoot 'requirements-runtime.lock'))
Invoke-Isolated $venvPython @('-m','pip','install','--disable-pip-version-check','--index-url','https://pypi.org/simple','--no-deps',$targetRoot)
Invoke-Isolated $venvPython @('-m','pip','check')
$cloudflared = $null
if (-not $SkipCloudflared) {
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'This package pins the Windows x64 cloudflared build.' }
    $tools = Join-Path $targetRoot 'tools'
    New-Item -ItemType Directory -Path $tools -Force | Out-Null
    $cloudflared = Join-Path $tools 'cloudflared.exe'
    $expected = '86aee4017b26625cee8484c113558f48effa4cd47f7aa05fcf425604e5d2b23c'
    if (-not (Test-Path -LiteralPath $cloudflared)) {
        $download = Join-Path $tools 'cloudflared.download'
        try {
            Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/cloudflare/cloudflared/releases/download/2026.10.0/cloudflared-windows-amd64.exe' -OutFile $download
            if ((Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw 'cloudflared checksum mismatch; installation stopped.' }
            Move-Item -LiteralPath $download -Destination $cloudflared
        } finally { if (Test-Path -LiteralPath $download) { Remove-Item -LiteralPath $download } }
    }
    if ((Get-FileHash -LiteralPath $cloudflared -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw 'Existing local cloudflared does not match the pinned checksum.' }
}
$initArgs = @('-m','grok_local_bridge.cli','--home',(Join-Path $targetRoot '.runtime'),'init')
if ($cloudflared) { $initArgs += @('--cloudflared',$cloudflared) }
Invoke-Isolated $venvPython $initArgs
Write-Output ('Installed in ' + $targetRoot + '. No Tunnel or public service started.')

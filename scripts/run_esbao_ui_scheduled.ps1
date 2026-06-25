param()

$ErrorActionPreference = "Continue"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$LogDir = Join-Path $ProjectRoot "reports\scheduled"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogPath = Join-Path $LogDir "esbao-ui-$Timestamp.log"

Set-Location $ProjectRoot

"[$(Get-Date -Format s)] Scheduled Esbao UI check started" | Tee-Object -FilePath $LogPath
"ProjectRoot=$ProjectRoot" | Tee-Object -FilePath $LogPath -Append

& (Join-Path $PSScriptRoot "run_esbao_ui.ps1") -EmailReport 2>&1 |
    Tee-Object -FilePath $LogPath -Append
$ExitCode = $LASTEXITCODE

"[$(Get-Date -Format s)] Scheduled Esbao UI check finished with exit code $ExitCode" |
    Tee-Object -FilePath $LogPath -Append
exit $ExitCode

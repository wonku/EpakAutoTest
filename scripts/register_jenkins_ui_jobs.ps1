param(
    [string]$JenkinsHome = "$env:ProgramData\Jenkins\.jenkins",
    [switch]$ReloadJenkins
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$SourceJobsRoot = Join-Path $RepoRoot "jenkins\jobs"
$TargetJobsRoot = Join-Path $JenkinsHome "jobs"

if (-not (Test-Path $SourceJobsRoot)) {
    throw "Job templates not found: $SourceJobsRoot"
}

$jobNames = @(
    "Pyautotest-Epak-UI",
    "Pyautotest-Esbao-UI"
)

foreach ($jobName in $jobNames) {
    $sourceDir = Join-Path $SourceJobsRoot $jobName
    $targetDir = Join-Path $TargetJobsRoot $jobName
    $sourceConfig = Join-Path $sourceDir "config.xml"

    if (-not (Test-Path $sourceConfig)) {
        throw "Missing job config: $sourceConfig"
    }

    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    Copy-Item -Path $sourceConfig -Destination (Join-Path $targetDir "config.xml") -Force

    $nextBuildNumberPath = Join-Path $targetDir "nextBuildNumber"
    if (-not (Test-Path $nextBuildNumberPath)) {
        Set-Content -Path $nextBuildNumberPath -Value "1" -NoNewline
    }

    Write-Output "Registered Jenkins job: $jobName"
}

if ($ReloadJenkins) {
    try {
        Invoke-WebRequest -Uri "http://localhost:8080/reload" -Method POST -UseBasicParsing -TimeoutSec 15 | Out-Null
        Write-Output "Jenkins configuration reloaded."
    }
    catch {
        Write-Warning "Could not reload Jenkins automatically. Open http://localhost:8080/reload or restart the Jenkins service."
    }
}

Write-Output "Done. Jobs should appear at http://localhost:8080/ after reload."

param(
    [Parameter(Position = 0)]
    [string]$AccountId,

    [string]$Url = "https://www.xiaohongshu.com",

    [string]$ChromePath
)

function Show-Usage {
    Write-Host "Usage:"
    Write-Host "  .\scripts\open_profile.ps1 <account_id> [-Url <url>] [-ChromePath <chrome.exe>]"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\scripts\open_profile.ps1 xhs_dev_01"
    Write-Host "  .\scripts\open_profile.ps1 xhs_dev_01 -Url `"chrome://version`""
}

if ([string]::IsNullOrWhiteSpace($AccountId)) {
    Show-Usage
    exit 1
}

$scriptDir = $PSScriptRoot
$browserWorkerRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
$profileRoot = Join-Path $browserWorkerRoot ".local_profiles"
$profilePath = Join-Path $profileRoot $AccountId

if ([string]::IsNullOrWhiteSpace($ChromePath)) {
    $chromeCandidates = @()

    if ($env:ProgramFiles) {
        $chromeCandidates += Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"
    }

    if (${env:ProgramFiles(x86)}) {
        $chromeCandidates += Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe"
    }

    if ($env:LOCALAPPDATA) {
        $chromeCandidates += Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe"
    }

    $ChromePath = $chromeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}

if ([string]::IsNullOrWhiteSpace($ChromePath) -or -not (Test-Path -LiteralPath $ChromePath)) {
    Write-Error "Chrome executable not found. Pass -ChromePath with the full path to chrome.exe."
    exit 1
}

New-Item -ItemType Directory -Force -Path $profilePath | Out-Null

$resolvedChromePath = (Resolve-Path -LiteralPath $ChromePath).Path
$resolvedProfilePath = (Resolve-Path -LiteralPath $profilePath).Path

Write-Host "Opening Chrome profile"
Write-Host "account_id: $AccountId"
Write-Host "profile_path: $resolvedProfilePath"
Write-Host "url: $Url"

$chromeArgs = @(
    "--user-data-dir=`"$resolvedProfilePath`"",
    "--profile-directory=`"Default`"",
    $Url
)

Start-Process -FilePath $resolvedChromePath -ArgumentList $chromeArgs

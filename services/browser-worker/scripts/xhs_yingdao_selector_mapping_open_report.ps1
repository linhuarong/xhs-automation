param(
    [Parameter(Mandatory = $true)]
    [string]$ReportPath
)

$ErrorActionPreference = "Stop"

$normalized = $ReportPath.Trim()
if ($normalized -match "^https?://") {
    Write-Error "Refusing to open http:// or https:// URLs. Only local selector mapping reports are allowed."
    exit 1
}

if ($normalized.ToLowerInvariant().Contains("xiaohongshu.com")) {
    Write-Error "Refusing to open a path containing xiaohongshu.com."
    exit 1
}

$resolved = Resolve-Path -LiteralPath $normalized
$fullPath = $resolved.Path
$lowerFullPath = $fullPath.ToLowerInvariant()
$requiredSegment = ".local_rpa_queue\yingdao\selector_mapping"

if (-not $lowerFullPath.Contains($requiredSegment)) {
    Write-Error "Refusing to open non-selector-mapping file. Path must be under .local_rpa_queue\yingdao\selector_mapping."
    exit 1
}

if ([System.IO.Path]::GetFileName($fullPath).ToLowerInvariant() -ne "selector_mapping_report.md") {
    Write-Error "Refusing to open unexpected file. Expected selector_mapping_report.md."
    exit 1
}

notepad $fullPath

param(
    [Parameter(Mandatory = $true)]
    [string]$HtmlPath
)

$ErrorActionPreference = "Stop"

$normalized = $HtmlPath.Trim()
if ($normalized -match "^https?://") {
    Write-Error "Refusing to open http:// or https:// URLs. Only local sandbox HTML files are allowed."
    exit 1
}

if ($normalized.ToLowerInvariant().Contains("xiaohongshu.com")) {
    Write-Error "Refusing to open a path containing xiaohongshu.com."
    exit 1
}

$resolved = Resolve-Path -LiteralPath $normalized
$fullPath = $resolved.Path
$lowerFullPath = $fullPath.ToLowerInvariant()
$requiredSegment = ".local_rpa_queue\yingdao\sandbox"

if (-not $lowerFullPath.Contains($requiredSegment)) {
    Write-Error "Refusing to open non-sandbox file. Path must be under .local_rpa_queue\yingdao\sandbox."
    exit 1
}

if ([System.IO.Path]::GetExtension($fullPath).ToLowerInvariant() -ne ".html") {
    Write-Error "Refusing to open non-HTML file."
    exit 1
}

Start-Process -FilePath $fullPath

param(
  [string]$HtmlPath = "",
  [string]$HtmlUri = ""
)

$ErrorActionPreference = "Stop"

if (-not $HtmlPath -and -not $HtmlUri) {
  Write-Error "Provide -HtmlPath or -HtmlUri."
  exit 1
}

$target = if ($HtmlPath) { $HtmlPath } else { $HtmlUri }
$lower = $target.ToLowerInvariant()

if ($lower.StartsWith("http://") -or $lower.StartsWith("https://")) {
  Write-Error "Refusing to open http/https URL."
  exit 1
}
if ($lower.Contains("xiaohongshu.com")) {
  Write-Error "Refusing to open Xiaohongshu URL or path."
  exit 1
}

if ($HtmlUri) {
  $uri = [System.Uri]$HtmlUri
  if ($uri.Scheme -ne "file") {
    Write-Error "Only file:// URIs are allowed."
    exit 1
  }
  $targetPath = $uri.LocalPath
} else {
  $targetPath = $HtmlPath
}

$resolved = Resolve-Path -LiteralPath $targetPath -ErrorAction Stop
$fullPath = $resolved.Path
$normalized = $fullPath.ToLowerInvariant()
$requiredSegment = [System.IO.Path]::Combine(".local_rpa_queue", "yingdao", "sandbox").ToLowerInvariant()

if (-not $normalized.Contains($requiredSegment)) {
  Write-Error "Refusing to open files outside .local_rpa_queue\yingdao\sandbox."
  exit 1
}
if ([System.IO.Path]::GetExtension($fullPath).ToLowerInvariant() -ne ".html") {
  Write-Error "Only local .html sandbox files are allowed."
  exit 1
}

Start-Process -FilePath $fullPath

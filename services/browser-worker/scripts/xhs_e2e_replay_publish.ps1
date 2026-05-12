param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [Parameter(Mandatory = $true)][string]$RunId,
  [Parameter(Mandatory = $true)][string]$JobId,
  [Parameter(Mandatory = $true)][string]$AccountId,
  [Parameter(Mandatory = $true)][string]$Title,
  [Parameter(Mandatory = $true)][string]$Body,
  [string]$Tags = "",
  [string]$ImagePaths = "",
  [string]$PublishMode = "manual_review"
)

$ErrorActionPreference = "Stop"

if ($BaseUrl -notmatch '^http://(127\.0\.0\.1|localhost)(:\d+)?$') {
  Write-Error "BaseUrl must point to local browser-worker only."
  exit 1
}

$tagList = @()
if (-not [string]::IsNullOrWhiteSpace($Tags)) {
  $tagList = @(
    $Tags -split "\s*,\s*" |
      ForEach-Object { $_.Trim() } |
      Where-Object { $_.Length -gt 0 }
  )
}

$imagePathList = @()
if (-not [string]::IsNullOrWhiteSpace($ImagePaths)) {
  $imagePathList = @(
    $ImagePaths -split "\s*,\s*" |
      ForEach-Object { $_.Trim() } |
      Where-Object { $_.Length -gt 0 }
  )
}

$payload = @{
  run_id = $RunId
  job_id = $JobId
  account_id = $AccountId
  title = $Title
  body = $Body
  tags = @($tagList)
  image_paths = @($imagePathList)
  publish_mode = $PublishMode
}

$bodyJson = $payload | ConvertTo-Json -Depth 8
$bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyJson)

$url = "$BaseUrl/api/workflows/xhs/e2e-replay/publish"

$response = Invoke-RestMethod `
  -Method Post `
  -Uri $url `
  -ContentType "application/json; charset=utf-8" `
  -Body $bodyBytes

$response | ConvertTo-Json -Depth 20
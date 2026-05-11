param(
  [ValidateSet("search", "publish")]
  [string]$JobType = "search",
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [Parameter(Mandatory = $true)]
  [string]$JobId,
  [Parameter(Mandatory = $true)]
  [string]$AccountId,
  [string]$Keyword = "",
  [int]$Limit = 20,
  [string]$Title = "",
  [string]$Body = "",
  [string]$Tags = "",
  [string]$ImagePaths = "",
  [string]$PublishMode = "manual_review"
)

$ErrorActionPreference = "Stop"

# Local-only replay all. This never calls real n8n, real OpenClaw, open shop, or Xiaohongshu.

if ($JobType -eq "search") {
  $endpoint = "$BaseUrl/api/workflows/xhs/contract-replay/all/search"
  $payload = @{
    job_id = $JobId
    account_id = $AccountId
    keyword = $Keyword
    limit = $Limit
  }
} else {
  $tagList = @()
  if ($Tags.Trim().Length -gt 0) {
    $tagList = $Tags.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
  }
  $imageList = @()
  if ($ImagePaths.Trim().Length -gt 0) {
    $imageList = $ImagePaths.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
  }
  $endpoint = "$BaseUrl/api/workflows/xhs/contract-replay/all/publish"
  $payload = @{
    job_id = $JobId
    account_id = $AccountId
    title = $Title
    body = $Body
    tags = $tagList
    image_paths = $imageList
    publish_mode = $PublishMode
  }
}

$json = $payload | ConvertTo-Json -Depth 10
$result = Invoke-RestMethod -Method Post -Uri $endpoint -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($json))

Write-Host "status: $($result.status)"
Write-Host "strict_binding_status: $($result.strict_binding_status)"
if ($result.n8n_replay) {
  Write-Host "n8n_replay_status: $($result.n8n_replay.status)"
  Write-Host "n8n_replay_result_path: $($result.n8n_replay.replay_result_path)"
}
if ($result.openclaw_replay) {
  Write-Host "openclaw_replay_status: $($result.openclaw_replay.status)"
  Write-Host "openclaw_replay_result_path: $($result.openclaw_replay.replay_result_path)"
}
if ($result.error_code) {
  Write-Host "error_code: $($result.error_code)"
  Write-Host "error_message: $($result.error_message)"
  exit 1
}

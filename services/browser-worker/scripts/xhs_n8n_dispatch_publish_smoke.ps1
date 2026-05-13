param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [Parameter(Mandatory = $true)][string]$JobId,
  [Parameter(Mandatory = $true)][string]$AccountId,
  [string]$Title = "XHS_SMOKE Task46",
  [string]$Body = "XHS_SMOKE Task46 dry-run publish body",
  [string[]]$Tags = @("XHS_SMOKE", "Task46"),
  [string[]]$ImagePaths = @()
)

$ErrorActionPreference = "Stop"

if ($BaseUrl -notmatch '^http://(127\.0\.0\.1|localhost)(:\d+)?$') {
  Write-Error "BaseUrl must point to local browser-worker only. Real n8n webhooks are forbidden for this smoke."
  exit 1
}

$body = @{
  job_id = $JobId
  account_id = $AccountId
  trigger_source = "n8n_smoke"
  dry_run = $true
  base_url = $BaseUrl
  payload = @{
    title = $Title
    body = $Body
    tags = $Tags
    image_paths = $ImagePaths
    publish_mode = "manual_review"
    dry_run = $true
  }
}

$response = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/workflows/xhs/n8n-dispatch/publish" -ContentType "application/json; charset=utf-8" -Body ($body | ConvertTo-Json -Depth 10)

Write-Host "n8n publish dispatch dry-run completed."
Write-Host "request_path=$($response.request_path)"
Write-Host "result_path=$($response.result_path)"
Write-Host "summary_path=$($response.summary_path)"
Write-Host "status=$($response.status)"

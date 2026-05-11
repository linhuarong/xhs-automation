param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [Parameter(Mandatory = $true)][string]$RunId,
  [Parameter(Mandatory = $true)][string]$JobId,
  [Parameter(Mandatory = $true)][string]$AccountId,
  [Parameter(Mandatory = $true)][string]$Keyword,
  [int]$Limit = 20
)

$ErrorActionPreference = "Stop"

if ($BaseUrl -notmatch '^http://(127\.0\.0\.1|localhost)(:\d+)?$') {
  Write-Error "BaseUrl must point to local browser-worker only."
  exit 1
}

$body = @{
  run_id = $RunId
  job_id = $JobId
  account_id = $AccountId
  keyword = $Keyword
  limit = $Limit
} | ConvertTo-Json -Depth 8

$url = "$BaseUrl/api/workflows/xhs/e2e-replay/search"
$response = Invoke-RestMethod -Method Post -Uri $url -ContentType "application/json; charset=utf-8" -Body $body
$response | ConvertTo-Json -Depth 20

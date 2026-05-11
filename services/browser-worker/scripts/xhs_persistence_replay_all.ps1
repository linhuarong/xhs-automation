param(
  [ValidateSet("search","publish")][string]$JobType = "search",
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [Parameter(Mandatory=$true)][string]$JobId,
  [Parameter(Mandatory=$true)][string]$AccountId
)

$ErrorActionPreference = "Stop"
$body = @{
  job_id = $JobId
  account_id = $AccountId
} | ConvertTo-Json -Depth 8

$result = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/workflows/xhs/persistence-replay/all/$JobType" -ContentType "application/json" -Body $body
$result | ConvertTo-Json -Depth 12

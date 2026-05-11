param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [Parameter(Mandatory = $true)]
  [string]$JobId,
  [Parameter(Mandatory = $true)]
  [string]$AccountId,
  [Parameter(Mandatory = $true)]
  [string]$Keyword,
  [int]$Limit = 20
)

$ErrorActionPreference = "Stop"

# Local-only contract replay. This calls browser-worker mock contract routes only; it does not call real n8n.

$endpoint = "$BaseUrl/api/workflows/xhs/contract-replay/n8n/search"
$payload = @{
  job_id = $JobId
  account_id = $AccountId
  keyword = $Keyword
  limit = $Limit
}

$json = $payload | ConvertTo-Json -Depth 10
$result = Invoke-RestMethod -Method Post -Uri $endpoint -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($json))

Write-Host "status: $($result.status)"
Write-Host "target: $($result.target)"
Write-Host "local_route: $($result.local_route)"
Write-Host "replay_payload_path: $($result.replay_payload_path)"
Write-Host "replay_result_path: $($result.replay_result_path)"
Write-Host "replay_summary_path: $($result.replay_summary_path)"
if ($result.error_code) {
  Write-Host "error_code: $($result.error_code)"
  Write-Host "error_message: $($result.error_message)"
  exit 1
}

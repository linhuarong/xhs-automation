param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [Parameter(Mandatory = $true)][string]$JobId,
  [Parameter(Mandatory = $true)][string]$AccountId,
  [switch]$DryRun,
  [string]$PersistencePayloadPath = ""
)

$ErrorActionPreference = "Stop"

if ($BaseUrl -notmatch '^http://(127\.0\.0\.1|localhost)(:\d+)?$') {
  Write-Error "BaseUrl must point to local browser-worker only."
  exit 1
}

$body = @{
  job_id = $JobId
  account_id = $AccountId
  dry_run = $true
  require_safe_payload = $true
} 
if (-not [string]::IsNullOrWhiteSpace($PersistencePayloadPath)) {
  $body.persistence_payload_path = $PersistencePayloadPath
}

$response = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/workflows/xhs/postgres-persistence/search" -ContentType "application/json; charset=utf-8" -Body ($body | ConvertTo-Json -Depth 8)
$response | ConvertTo-Json -Depth 20

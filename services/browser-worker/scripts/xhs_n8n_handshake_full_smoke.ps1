param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [Parameter(Mandatory = $true)][string]$HandshakeId,
  [Parameter(Mandatory = $true)][string]$JobId,
  [string]$AccountId = "xhs_dev_01",
  [string]$WebhookUrl = "",
  [switch]$RealHandshake
)

$ErrorActionPreference = "Stop"

if ($BaseUrl -notmatch '^http://(127\.0\.0\.1|localhost)(:\d+)?$') {
  Write-Error "BaseUrl must point to local browser-worker only."
  exit 1
}

if ($RealHandshake) {
  if ($env:XHS_N8N_HANDSHAKE_ENABLED -ne "true" -or $env:XHS_ALLOW_REAL_N8N_HANDSHAKE -ne "true") {
    Write-Error "Real handshake requires XHS_N8N_HANDSHAKE_ENABLED=true and XHS_ALLOW_REAL_N8N_HANDSHAKE=true."
    exit 1
  }
  if ([string]::IsNullOrWhiteSpace($WebhookUrl) -and [string]::IsNullOrWhiteSpace($env:XHS_N8N_HANDSHAKE_WEBHOOK_URL)) {
    Write-Error "Real handshake requires a webhook URL from parameter or environment."
    exit 1
  }
}

$body = @{
  handshake_id = $HandshakeId
  job_id = $JobId
  account_id = $AccountId
  dry_run = -not $RealHandshake
  marker = "XHS_N8N_HANDSHAKE_SMOKE"
  payload = @{
    marker = "XHS_N8N_HANDSHAKE_SMOKE"
    dry_run = -not $RealHandshake
    scope = "full"
  }
}

if (-not [string]::IsNullOrWhiteSpace($WebhookUrl)) {
  $body.webhook_url = $WebhookUrl
}

$response = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/workflows/xhs/n8n-handshake/full" -ContentType "application/json; charset=utf-8" -Body ($body | ConvertTo-Json -Depth 10)

Write-Host "n8n full handshake smoke completed."
Write-Host "request_path=$($response.request_path)"
Write-Host "response_path=$($response.response_path)"
Write-Host "summary_path=$($response.summary_path)"
Write-Host "status=$($response.status)"

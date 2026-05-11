param(
    [Parameter(Mandatory = $true)][ValidateSet("search", "publish")][string]$JobType,
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [Parameter(Mandatory = $true)][string]$JobId
)

$ErrorActionPreference = "Stop"
$endpoint = "$BaseUrl/api/workflows/xhs/yingdao/desktop-smoke/$JobType/$JobId/verify"
$result = Invoke-RestMethod -Method Get -Uri $endpoint
$result | ConvertTo-Json -Depth 20
Write-Host "status: $($result.status)"
Write-Host "receipt_valid: $($result.summary.receipt_valid)"
Write-Host "evidence_valid: $($result.summary.evidence_valid)"
Write-Host "opened_browser: $($result.summary.opened_browser)"
Write-Host "opened_xhs: $($result.summary.opened_xhs)"
Write-Host "real_action_executed: $($result.summary.real_action_executed)"

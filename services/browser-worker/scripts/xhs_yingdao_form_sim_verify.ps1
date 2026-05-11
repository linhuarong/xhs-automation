param(
    [Parameter(Mandatory = $true)][ValidateSet("search", "publish")][string]$JobType,
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [Parameter(Mandatory = $true)][string]$JobId
)

$ErrorActionPreference = "Stop"
$endpoint = "$BaseUrl/api/workflows/xhs/yingdao/form-simulator/$JobType/$JobId/verify"
$result = Invoke-RestMethod -Method Get -Uri $endpoint
$result | ConvertTo-Json -Depth 20
Write-Host "status: $($result.status)"
Write-Host "trace_valid: $($result.summary.trace_valid)"
Write-Host "result_valid: $($result.summary.result_valid)"
Write-Host "opened_browser: $($result.summary.opened_browser)"
Write-Host "opened_xhs: $($result.summary.opened_xhs)"
Write-Host "called_external_api: $($result.summary.called_external_api)"
Write-Host "clicked_real_publish: $($result.summary.clicked_real_publish)"

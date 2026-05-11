param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("search", "publish")]
    [string]$JobType,

    [string]$BaseUrl = "http://127.0.0.1:8000",

    [Parameter(Mandatory = $true)]
    [string]$JobId
)

$ErrorActionPreference = "Stop"

$endpoint = "$BaseUrl/api/workflows/xhs/yingdao/html-sandbox/$JobType/$JobId/verify"
$response = Invoke-RestMethod -Method Get -Uri $endpoint

Write-Host "status: $($response.status)"
Write-Host "trace_valid: $($response.summary.trace_valid)"
Write-Host "result_valid: $($response.summary.result_valid)"
Write-Host "opened_external_url: $($response.summary.opened_external_url)"
Write-Host "opened_xhs: $($response.summary.opened_xhs)"
Write-Host "error_code: $($response.error_code)"
Write-Host "message: $($response.message)"

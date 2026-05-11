param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("search", "publish")]
    [string]$JobType,

    [string]$BaseUrl = "http://127.0.0.1:8000",

    [Parameter(Mandatory = $true)]
    [string]$JobId
)

$ErrorActionPreference = "Stop"

$endpoint = "$BaseUrl/api/workflows/xhs/yingdao/selector-mapping/$JobType/$JobId/verify"
$response = Invoke-RestMethod -Method Get -Uri $endpoint

Write-Host "status: $($response.status)"
Write-Host "confirmation_valid: $($response.summary.confirmation_valid)"
Write-Host "confirmed_selector_count: $($response.summary.confirmed_selector_count)"
Write-Host "opened_external_url: $($response.summary.opened_external_url)"
Write-Host "opened_xhs: $($response.summary.opened_xhs)"
Write-Host "error_code: $($response.error_code)"
Write-Host "message: $($response.message)"

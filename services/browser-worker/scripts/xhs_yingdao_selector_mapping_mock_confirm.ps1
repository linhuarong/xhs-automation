param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("search", "publish")]
    [string]$JobType,

    [string]$BaseUrl = "http://127.0.0.1:8000",

    [Parameter(Mandatory = $true)]
    [string]$JobId,

    [string]$Status = "success"
)

$ErrorActionPreference = "Stop"

$endpoint = "$BaseUrl/api/workflows/xhs/yingdao/selector-mapping/$JobType/$JobId/mock-confirm"
$payload = @{ status = $Status }
$response = Invoke-RestMethod -Method Post -Uri $endpoint -ContentType "application/json" -Body ($payload | ConvertTo-Json -Depth 4)

Write-Host "status: $($response.status)"
Write-Host "confirmation_path: $($response.confirmation_path)"
Write-Host "message: $($response.message)"

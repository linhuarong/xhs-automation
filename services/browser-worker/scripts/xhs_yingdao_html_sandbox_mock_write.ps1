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

$endpoint = "$BaseUrl/api/workflows/xhs/yingdao/html-sandbox/$JobType/$JobId/mock-write"
$payload = @{ status = $Status }
$response = Invoke-RestMethod -Method Post -Uri $endpoint -ContentType "application/json" -Body ($payload | ConvertTo-Json -Depth 4)

Write-Host "status: $($response.status)"
Write-Host "trace_path: $($response.trace_path)"
Write-Host "result_path: $($response.result_path)"
Write-Host "message: $($response.message)"

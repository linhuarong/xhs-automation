param(
    [Parameter(Mandatory = $true)][ValidateSet("search", "publish")][string]$JobType,
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [Parameter(Mandatory = $true)][string]$JobId,
    [string]$Status = "success"
)

$ErrorActionPreference = "Stop"
$endpoint = "$BaseUrl/api/workflows/xhs/yingdao/form-simulator/$JobType/$JobId/mock-write"
$payload = @{ status = $Status } | ConvertTo-Json -Depth 10
$result = Invoke-RestMethod -Method Post -Uri $endpoint -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($payload))
$result | ConvertTo-Json -Depth 20
Write-Host "trace_path: $($result.trace_path)"
Write-Host "result_path: $($result.result_path)"
Write-Host "Local mock-write only. No browser, local HTML, Xiaohongshu, Yingdao OpenAPI, Feishu, PostgreSQL, or MinIO call is made."

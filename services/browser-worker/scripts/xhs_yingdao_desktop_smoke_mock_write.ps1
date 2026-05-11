param(
    [Parameter(Mandatory = $true)][ValidateSet("search", "publish")][string]$JobType,
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [Parameter(Mandatory = $true)][string]$JobId,
    [string]$Status = "success"
)

$ErrorActionPreference = "Stop"
$endpoint = "$BaseUrl/api/workflows/xhs/yingdao/desktop-smoke/$JobType/$JobId/mock-write"
$payload = @{ status = $Status } | ConvertTo-Json -Depth 10
$result = Invoke-RestMethod -Method Post -Uri $endpoint -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($payload))
$result | ConvertTo-Json -Depth 20
Write-Host "receipt_path: $($result.receipt_path)"
Write-Host "evidence_path: $($result.evidence_path)"
Write-Host "Local mock-write only. No Yingdao OpenAPI, browser, XHS, Feishu, PostgreSQL, or MinIO call is made."

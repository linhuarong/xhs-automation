param(
    [string]$ApiBaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
Invoke-RestMethod `
    -Method Get `
    -Uri "$ApiBaseUrl/api/workflows/xhs/health"

param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$endpoint = "$BaseUrl/api/workflows/xhs/yingdao/local-handoff/active"
$result = Invoke-RestMethod -Method Get -Uri $endpoint
$result | ConvertTo-Json -Depth 10

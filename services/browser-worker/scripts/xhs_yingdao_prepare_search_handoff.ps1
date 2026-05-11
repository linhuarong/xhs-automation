param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [Parameter(Mandatory = $true)][string]$JobId,
    [Parameter(Mandatory = $true)][string]$AccountId,
    [Parameter(Mandatory = $true)][string]$Keyword,
    [int]$Limit = 20
)

$ErrorActionPreference = "Stop"
$endpoint = "$BaseUrl/api/workflows/xhs/yingdao/local-handoff/search"
$body = @{
    job_id = $JobId
    account_id = $AccountId
    provider_type = "yingdao_local_file_trigger"
    keyword = $Keyword
    limit = $Limit
    capture_screenshot = $true
} | ConvertTo-Json -Depth 10

$result = Invoke-RestMethod -Method Post -Uri $endpoint -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
$result | ConvertTo-Json -Depth 10
Write-Host "active_job_path: $($result.active_job_path)"
Write-Host "expected_evidence_path: $($result.expected_evidence_path)"

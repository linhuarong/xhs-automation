param(
    [Parameter(Mandatory = $true)]
    [string]$JobId,

    [Parameter(Mandatory = $true)]
    [string]$JobType,

    [string]$ApiBaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$body = @{
    job_id = $JobId
    job_type = $JobType
} | ConvertTo-Json -Depth 4

Invoke-RestMethod `
    -Method Post `
    -Uri "$ApiBaseUrl/api/webhooks/openclaw/xhs/job-status" `
    -ContentType "application/json; charset=utf-8" `
    -Body $body

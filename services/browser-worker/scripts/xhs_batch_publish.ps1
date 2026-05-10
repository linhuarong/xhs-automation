param(
    [Parameter(Mandatory = $true)]
    [string]$BatchId,

    [Parameter(Mandatory = $true)]
    [string]$AccountId,

    [Parameter(Mandatory = $true)]
    [string]$ProviderType,

    [Parameter(Mandatory = $true)]
    [string]$JobsJsonPath,

    [string]$ApiBaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$jobs = Get-Content -Raw -Encoding UTF8 $JobsJsonPath | ConvertFrom-Json
$body = @{
    batch_id = $BatchId
    account_id = $AccountId
    provider_type = $ProviderType
    jobs = @($jobs)
    mode = "sync"
} | ConvertTo-Json -Depth 12

Invoke-RestMethod `
    -Method Post `
    -Uri "$ApiBaseUrl/api/xhs/publish/batch" `
    -ContentType "application/json; charset=utf-8" `
    -Body $body

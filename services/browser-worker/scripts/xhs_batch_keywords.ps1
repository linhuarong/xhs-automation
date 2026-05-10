param(
    [Parameter(Mandatory = $true)]
    [string]$BatchId,

    [Parameter(Mandatory = $true)]
    [string]$AccountId,

    [Parameter(Mandatory = $true)]
    [string]$ProviderType,

    [Parameter(Mandatory = $true)]
    [string]$Keywords,

    [int]$Limit = 20,

    [string]$ApiBaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$keywordList = $Keywords.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
$body = @{
    batch_id = $BatchId
    account_id = $AccountId
    provider_type = $ProviderType
    keywords = @($keywordList)
    limit = $Limit
    mode = "sync"
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
    -Method Post `
    -Uri "$ApiBaseUrl/api/xhs/keywords/batch" `
    -ContentType "application/json; charset=utf-8" `
    -Body $body

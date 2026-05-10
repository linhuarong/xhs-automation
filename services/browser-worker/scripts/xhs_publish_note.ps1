param(
    [Parameter(Mandatory = $true)]
    [string]$JobId,

    [Parameter(Mandatory = $true)]
    [string]$AccountId,

    [Parameter(Mandatory = $true)]
    [string]$ProviderType,

    [Parameter(Mandatory = $true)]
    [string]$Title,

    [Parameter(Mandatory = $true)]
    [string]$Body,

    [string]$Tags = "",
    [string]$AssetPaths = "",
    [string]$ApiBaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$tagList = $Tags.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
$assetList = @()
$order = 1
$AssetPaths.Split(",") | ForEach-Object {
    $path = $_.Trim()
    if ($path) {
        $assetList += @{
            local_path = $path
            order = $order
            asset_type = "image"
        }
        $order += 1
    }
}

$bodyJson = @{
    job_id = $JobId
    account_id = $AccountId
    provider_type = $ProviderType
    title = $Title
    body = $Body
    tags = @($tagList)
    assets = @($assetList)
} | ConvertTo-Json -Depth 8

Invoke-RestMethod `
    -Method Post `
    -Uri "$ApiBaseUrl/api/xhs/publish" `
    -ContentType "application/json; charset=utf-8" `
    -Body $bodyJson

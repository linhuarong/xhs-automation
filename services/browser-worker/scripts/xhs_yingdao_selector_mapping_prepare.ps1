param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("search", "publish")]
    [string]$JobType,

    [string]$BaseUrl = "http://127.0.0.1:8000",

    [Parameter(Mandatory = $true)]
    [string]$JobId,

    [Parameter(Mandatory = $true)]
    [string]$AccountId,

    [string]$Keyword,
    [int]$Limit = 20,
    [string]$Title,
    [string]$Body,
    [string]$Tags = "",
    [string]$ImagePaths = "",
    [string]$PublishMode = "manual_review"
)

$ErrorActionPreference = "Stop"

if ($JobType -eq "search") {
    $endpoint = "$BaseUrl/api/workflows/xhs/yingdao/selector-mapping/search/prepare"
    $payload = @{
        job_id = $JobId
        account_id = $AccountId
        keyword = $Keyword
        limit = $Limit
    }
} else {
    $endpoint = "$BaseUrl/api/workflows/xhs/yingdao/selector-mapping/publish/prepare"
    $tagList = @()
    if ($Tags.Trim().Length -gt 0) {
        $tagList = $Tags.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    }
    $imageList = @()
    if ($ImagePaths.Trim().Length -gt 0) {
        $imageList = $ImagePaths.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    }
    $payload = @{
        job_id = $JobId
        account_id = $AccountId
        title = $Title
        body = $Body
        tags = $tagList
        image_paths = $imageList
        publish_mode = $PublishMode
    }
}

$response = Invoke-RestMethod -Method Post -Uri $endpoint -ContentType "application/json" -Body ($payload | ConvertTo-Json -Depth 8)

Write-Host "status: $($response.status)"
Write-Host "mapping_dir: $($response.mapping_dir)"
Write-Host "selector_mapping_path: $($response.selector_mapping_path)"
Write-Host "action_sequence_path: $($response.action_sequence_path)"
Write-Host "mapping_report_path: $($response.mapping_report_path)"

param(
    [Parameter(Mandatory = $true)][ValidateSet("search", "publish")][string]$JobType,
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [Parameter(Mandatory = $true)][string]$JobId,
    [Parameter(Mandatory = $true)][string]$AccountId,
    [string]$Keyword = "",
    [int]$Limit = 20,
    [string]$Title = "",
    [string]$Body = "",
    [string]$Tags = "",
    [string]$ImagePaths = "",
    [string]$PublishMode = "manual_review"
)

$ErrorActionPreference = "Stop"
if ($JobType -eq "search") {
    $endpoint = "$BaseUrl/api/workflows/xhs/yingdao/form-simulator/search/prepare"
    $payload = @{
        job_id = $JobId
        account_id = $AccountId
        keyword = $Keyword
        limit = $Limit
    }
} else {
    $endpoint = "$BaseUrl/api/workflows/xhs/yingdao/form-simulator/publish/prepare"
    $tagList = @()
    if ($Tags.Trim().Length -gt 0) {
        $tagList = $Tags.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_.Length -gt 0 }
    }
    $imagePathList = @()
    if ($ImagePaths.Trim().Length -gt 0) {
        $imagePathList = $ImagePaths.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_.Length -gt 0 }
    }
    $payload = @{
        job_id = $JobId
        account_id = $AccountId
        title = $Title
        body = $Body
        tags = @($tagList)
        image_paths = @($imagePathList)
        publish_mode = $PublishMode
    }
}

$json = $payload | ConvertTo-Json -Depth 20
$result = Invoke-RestMethod -Method Post -Uri $endpoint -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($json))
$result | ConvertTo-Json -Depth 20
Write-Host "simulator_dir: $($result.simulator_dir)"
Write-Host "form_spec_path: $($result.form_spec_path)"
Write-Host "expected_actions_path: $($result.expected_actions_path)"
Write-Host "Browserless simulator only. Do not open browser, local HTML, or Xiaohongshu."

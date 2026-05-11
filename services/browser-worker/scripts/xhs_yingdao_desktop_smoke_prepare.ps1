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
    [string]$ImagePaths = ""
)

$ErrorActionPreference = "Stop"
if ($JobType -eq "search") {
    $endpoint = "$BaseUrl/api/workflows/xhs/yingdao/desktop-smoke/search/prepare"
    $payload = @{
        job_id = $JobId
        account_id = $AccountId
        keyword = $Keyword
        limit = $Limit
    }
} else {
    $endpoint = "$BaseUrl/api/workflows/xhs/yingdao/desktop-smoke/publish/prepare"
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
    }
}

$json = $payload | ConvertTo-Json -Depth 20
$result = Invoke-RestMethod -Method Post -Uri $endpoint -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($json))
$result | ConvertTo-Json -Depth 20
Write-Host "active_job_path: $($result.active_job_path)"
Write-Host "expected_receipt_path: $($result.expected_receipt_path)"
Write-Host "expected_evidence_path: $($result.expected_evidence_path)"
Write-Host "Do not start any browser or XHS step in this smoke test."

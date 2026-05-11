param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [Parameter(Mandatory = $true)][string]$JobId,
    [Parameter(Mandatory = $true)][string]$AccountId,
    [Parameter(Mandatory = $true)][string]$Title,
    [Parameter(Mandatory = $true)][string]$Body,
    [string]$Tags = "",
    [string]$ImagePaths = ""
)

$ErrorActionPreference = "Stop"
$endpoint = "$BaseUrl/api/workflows/xhs/yingdao/local-handoff/publish"
$tagList = @()
if ($Tags.Trim().Length -gt 0) {
    $tagList = $Tags.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_.Length -gt 0 }
}
$imagePathList = @()
if ($ImagePaths.Trim().Length -gt 0) {
    $imagePathList = $ImagePaths.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_.Length -gt 0 }
}

$bodyJson = @{
    job_id = $JobId
    account_id = $AccountId
    provider_type = "yingdao_local_file_trigger"
    title = $Title
    body = $Body
    tags = @($tagList)
    image_paths = @($imagePathList)
    publish_mode = "manual_review"
} | ConvertTo-Json -Depth 10

$result = Invoke-RestMethod -Method Post -Uri $endpoint -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($bodyJson))
$result | ConvertTo-Json -Depth 10
Write-Host "active_job_path: $($result.active_job_path)"
Write-Host "expected_evidence_path: $($result.expected_evidence_path)"

$ErrorActionPreference = "Stop"

$BaseUrl = "http://127.0.0.1:8000"
$Keyword = "$([char]0x773C)$([char]0x5F71)"
$Title = "$([char]0x6D4B)$([char]0x8BD5)$([char]0x6807)$([char]0x9898)"
$Body = "$([char]0x6D4B)$([char]0x8BD5)$([char]0x6B63)$([char]0x6587)"

function Invoke-SmokeRequest {
    param (
        [string]$Step,
        [scriptblock]$Request
    )

    try {
        return & $Request
    }
    catch {
        Write-Error "Smoke test failed at ${Step}: $($_.Exception.Message)"
        exit 1
    }
}

$health = Invoke-SmokeRequest -Step "GET /health" -Request {
    Invoke-RestMethod -Method Get -Uri "$BaseUrl/health"
}

if ($health.status -ne "ok" -or $health.service -ne "xhs-browser-worker") {
    Write-Error "Smoke test failed at GET /health: unexpected response"
    exit 1
}

$searchBody = @{
    job_id = "search-smoke-1"
    account_id = "xhs_dev_01"
    keyword = $Keyword
} | ConvertTo-Json

$search = Invoke-SmokeRequest -Step "POST /api/xhs/search" -Request {
    Invoke-RestMethod `
        -Method Post `
        -Uri "$BaseUrl/api/xhs/search" `
        -ContentType "application/json" `
        -Body $searchBody
}

if ($search.job_id -ne "search-smoke-1" -or $search.status -ne "accepted") {
    Write-Error "Smoke test failed at POST /api/xhs/search: unexpected response"
    exit 1
}

$publishBody = @{
    job_id = "publish-smoke-1"
    account_id = "xhs_dev_01"
    title = $Title
    body = $Body
    tags = @($Keyword)
    images = @("https://example.com/image.png")
} | ConvertTo-Json

$publish = Invoke-SmokeRequest -Step "POST /api/xhs/publish" -Request {
    Invoke-RestMethod `
        -Method Post `
        -Uri "$BaseUrl/api/xhs/publish" `
        -ContentType "application/json" `
        -Body $publishBody
}

if ($publish.job_id -ne "publish-smoke-1" -or $publish.status -ne "accepted") {
    Write-Error "Smoke test failed at POST /api/xhs/publish: unexpected response"
    exit 1
}

$publishStatus = Invoke-SmokeRequest -Step "GET /api/xhs/publish/publish-smoke-1" -Request {
    Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/xhs/publish/publish-smoke-1"
}

if (
    $publishStatus.job_id -ne "publish-smoke-1" -or
    $publishStatus.task_type -ne "content_publish" -or
    $publishStatus.status -ne "accepted"
) {
    Write-Error "Smoke test failed at GET /api/xhs/publish/publish-smoke-1: unexpected response"
    exit 1
}

Write-Output "browser-worker smoke test passed"

param(
    [Parameter(Mandatory = $true)][ValidateSet("search", "publish")][string]$JobType,
    [Parameter(Mandatory = $true)][string]$JobId,
    [ValidateSet("success", "failed", "waiting_manual_review")][string]$Status = "success",
    [string]$QueueRoot = ".local_rpa_queue\yingdao"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path -Path "." -ErrorAction SilentlyContinue
if ($null -eq $root) {
    throw "current directory is not available"
}
$basePath = Join-Path -Path (Get-Location) -ChildPath $QueueRoot
$jobDir = Join-Path -Path $basePath -ChildPath "$JobType\jobs\$JobId"
New-Item -ItemType Directory -Force -Path $jobDir | Out-Null
$capturedAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

if ($JobType -eq "search") {
    $evidencePath = Join-Path -Path $jobDir -ChildPath "search_evidence.json"
    $payload = @{
        schema_version = "1.0"
        job_id = $JobId
        job_type = "xhs_search"
        task_type = "xhs_keyword_search"
        status = $Status
        keyword = "mock"
        account_id = "xhs_dev_01"
        provider_type = "yingdao_local_file_trigger"
        captured_at = $capturedAt
        screenshot_path = "search_success.png"
        item_count = 0
        normalized_record_count = 0
        result_area_found = $true
        items = @()
        normalized_records = @()
    }
} else {
    $evidencePath = Join-Path -Path $jobDir -ChildPath "publish_evidence.json"
    $payload = @{
        schema_version = "1.0"
        job_id = $JobId
        job_type = "xhs_publish"
        task_type = "xhs_content_publish"
        status = $Status
        account_id = "xhs_dev_01"
        provider_type = "yingdao_local_file_trigger"
        captured_at = $capturedAt
        title = "mock title"
        note_url = $null
        screenshots = @()
        screenshot_path = $null
        message = "publish form prepared, waiting manual review"
        error_code = $null
        error_message = $null
    }
}

$json = $payload | ConvertTo-Json -Depth 20
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($evidencePath, $json, $utf8NoBom)
Write-Host "mock evidence written: $evidencePath"

[CmdletBinding()]
param(
    [ValidateSet("search", "publish")]
    [string]$JobType = "search",
    [ValidateSet("create", "update")]
    [string]$Operation = "create",
    [Parameter(Mandatory=$true)][string]$JobId,
    [Parameter(Mandatory=$true)][string]$AccountId,
    [string]$FeishuRecordId = "",
    [switch]$RealWrite,
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

function Test-LocalBaseUrl {
    param([string]$Value)
    return $Value -match '^http://(127\.0\.0\.1|localhost)(:\d+)?$'
}

function Write-SmokeJson {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)]$Value
    )
    $parent = Split-Path -Parent $Path
    if ($parent) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    $json = $Value | ConvertTo-Json -Depth 20
    [System.IO.File]::WriteAllText($Path, $json, [System.Text.Encoding]::UTF8)
}

function Write-SmokeFailure {
    param(
        [Parameter(Mandatory=$true)][hashtable]$RequestDoc,
        [Parameter(Mandatory=$true)][string]$ErrorCode,
        [Parameter(Mandatory=$true)][string]$ErrorMessage
    )
    $resultDoc = [ordered]@{
        record_id = if ($FeishuRecordId) { $FeishuRecordId } else { $null }
        operation = $Operation
        dry_run = (-not $RealWrite)
        written_count = 0
        status = "failed"
        error_code = $ErrorCode
        error_message = $ErrorMessage
    }
    $summaryDoc = [ordered]@{
        job_id = $JobId
        job_type = $JobType
        operation = $Operation
        dry_run = (-not $RealWrite)
        real_write_requested = [bool]$RealWrite
        marker = "XHS_SMOKE"
        status = "failed"
        request_path = $RequestPath
        result_path = $ResultPath
        summary_path = $SummaryPath
        error_code = $ErrorCode
        error_message = $ErrorMessage
    }
    Write-SmokeJson -Path $RequestPath -Value $RequestDoc
    Write-SmokeJson -Path $ResultPath -Value $resultDoc
    Write-SmokeJson -Path $SummaryPath -Value $summaryDoc
    Write-Error $ErrorMessage
    exit 1
}

$WorkerRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$SmokeDir = Join-Path $WorkerRoot ".local_rpa_queue\feishu_smoke\$JobType\$JobId"
$RequestPath = Join-Path $SmokeDir "feishu_smoke_request.json"
$ResultPath = Join-Path $SmokeDir "feishu_smoke_result.json"
$SummaryPath = Join-Path $SmokeDir "feishu_smoke_summary.json"
$DryRun = -not $RealWrite
$Timestamp = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
$Marker = "XHS_SMOKE Task44 $Timestamp $JobId"

$requestDoc = [ordered]@{
    schema_version = "1.0"
    smoke_type = "feishu_controlled_real_write_smoke"
    job_type = $JobType
    job_id = $JobId
    account_id = $AccountId
    operation = $Operation
    dry_run = $DryRun
    real_write_requested = [bool]$RealWrite
    marker = "XHS_SMOKE"
    created_at = $Timestamp
    output_dir = $SmokeDir
}

if (-not (Test-LocalBaseUrl -Value $BaseUrl)) {
    Write-SmokeFailure -RequestDoc $requestDoc -ErrorCode "FEISHU_SMOKE_DISABLED" -ErrorMessage "BaseUrl must be local browser-worker API."
}

if ($Operation -eq "update" -and [string]::IsNullOrWhiteSpace($FeishuRecordId)) {
    Write-SmokeFailure -RequestDoc $requestDoc -ErrorCode "FEISHU_SMOKE_RECORD_ID_REQUIRED" -ErrorMessage "FeishuRecordId is required for update smoke."
}

if ($RealWrite) {
    if ($env:XHS_FEISHU_WRITE_ENABLED -ne "true" -or $env:XHS_ALLOW_REAL_FEISHU_WRITE -ne "true" -or $env:XHS_FEISHU_SMOKE_ENABLED -ne "true") {
        Write-SmokeFailure -RequestDoc $requestDoc -ErrorCode "FEISHU_SMOKE_DISABLED" -ErrorMessage "Real Feishu smoke requires explicit write and smoke environment flags."
    }
}

if ($JobType -eq "search") {
    $record = [ordered]@{
        job_id = $JobId
        account_id = $AccountId
        provider_type = "kuaijingvs_yingdao_rpa"
        keyword = "XHS_SMOKE Task44 keyword"
        rank = 1
        title = $Marker
        author = "XHS_SMOKE"
        note_id = "XHS_SMOKE-$JobId"
        note_url = ""
        metric_raw_text = "XHS_SMOKE"
        like_count_text = "0"
        status = "XHS_SMOKE Task44 smoke"
        error_code = $null
        error_message = $null
        captured_at = $Timestamp
    }
} else {
    $record = [ordered]@{
        job_id = $JobId
        account_id = $AccountId
        provider_type = "kuaijingvs_yingdao_rpa"
        title = "XHS_SMOKE Task44 $JobId"
        body = "XHS_SMOKE Task44 controlled smoke body $Timestamp"
        tags = @("XHS_SMOKE", "Task44")
        status = "XHS_SMOKE Task44 smoke"
        note_url = ""
        error_code = $null
        error_message = $null
        updated_at = $Timestamp
    }
}

$apiBody = [ordered]@{
    job_id = $JobId
    account_id = $AccountId
    operation = $Operation
    feishu_record_id = if ($FeishuRecordId) { $FeishuRecordId } else { $null }
    records = @($record)
    dry_run = $DryRun
}

$requestDoc["api_path"] = "/api/workflows/xhs/feishu-write/$JobType"
$requestDoc["record_count"] = 1
$requestDoc["payload_marker_present"] = $true
$requestDoc["feishu_record_id"] = if ($FeishuRecordId) { $FeishuRecordId } else { $null }

$payloadJson = $apiBody | ConvertTo-Json -Depth 20
if ($payloadJson -notmatch "XHS_SMOKE") {
    Write-SmokeFailure -RequestDoc $requestDoc -ErrorCode "FEISHU_SMOKE_MARKER_REQUIRED" -ErrorMessage "Smoke payload must contain XHS_SMOKE marker."
}

Write-SmokeJson -Path $RequestPath -Value $requestDoc

$uri = "$BaseUrl/api/workflows/xhs/feishu-write/$JobType"
$apiResult = Invoke-RestMethod -Method Post -Uri $uri -ContentType "application/json" -Body ([System.Text.Encoding]::UTF8.GetBytes($payloadJson))

$smokeResult = [ordered]@{
    record_id = if ($FeishuRecordId) { $FeishuRecordId } else { $null }
    operation = $Operation
    dry_run = $DryRun
    written_count = $apiResult.written_count
    status = $apiResult.status
    error_code = $apiResult.error_code
    error_message = $apiResult.error_message
}

$smokeSummary = [ordered]@{
    job_id = $JobId
    job_type = $JobType
    operation = $Operation
    dry_run = $DryRun
    real_write_requested = [bool]$RealWrite
    marker = "XHS_SMOKE"
    status = $apiResult.status
    written_count = $apiResult.written_count
    request_path = $RequestPath
    result_path = $ResultPath
    summary_path = $SummaryPath
    feishu_plan_path = $apiResult.plan_path
    feishu_payload_path = $apiResult.payload_path
    feishu_result_path = $apiResult.result_path
    feishu_summary_path = $apiResult.summary_path
    safety = [ordered]@{
        single_record_only = $true
        local_api_only = $true
        marker_required = $true
    }
}

Write-SmokeJson -Path $ResultPath -Value $smokeResult
Write-SmokeJson -Path $SummaryPath -Value $smokeSummary

Write-Host "Feishu controlled smoke completed."
Write-Host "status=$($smokeResult.status)"
Write-Host "dry_run=$DryRun"
Write-Host "written_count=$($smokeResult.written_count)"
Write-Host "request_path=$RequestPath"
Write-Host "result_path=$ResultPath"
Write-Host "summary_path=$SummaryPath"

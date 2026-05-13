[CmdletBinding()]
param(
    [ValidateSet("search", "publish")]
    [string]$JobType = "search",
    [ValidateSet("create", "update", "readback")]
    [string]$Operation = "readback",
    [Parameter(Mandatory=$true)][string]$JobId,
    [Parameter(Mandatory=$true)][string]$AccountId,
    [string]$FeishuRecordId = "",
    [switch]$RealWrite,
    [switch]$Readback,
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

function Test-LocalBaseUrl {
    param([string]$Value)
    return $Value -match '^http://(127\.0\.0\.1|localhost)(:\d+)?$'
}

function Write-JsonFile {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)]$Value
    )
    $parent = Split-Path -Parent $Path
    if ($parent) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    $json = $Value | ConvertTo-Json -Depth 30
    [System.IO.File]::WriteAllText($Path, $json, [System.Text.Encoding]::UTF8)
}

function Write-Failure {
    param(
        [Parameter(Mandatory=$true)][hashtable]$RequestDoc,
        [Parameter(Mandatory=$true)][string]$ErrorCode,
        [Parameter(Mandatory=$true)][string]$ErrorMessage
    )
    $expected = [ordered]@{}
    $actual = [ordered]@{}
    $check = [ordered]@{
        schema_version = "1.0"
        check_type = "controlled_feishu_readback_check"
        job_id = $JobId
        job_type = $JobType
        operation = $Operation
        dry_run = (-not ($RealWrite -and $Readback))
        record_id = if ($FeishuRecordId) { $FeishuRecordId } else { $null }
        expected_fields = $expected
        actual_fields = $actual
        matched_fields = @()
        missing_fields = @()
        mismatched_fields = @()
        extra_fields = @()
        check_passed = $false
        error_code = $ErrorCode
        error_message = $ErrorMessage
    }
    $summary = [ordered]@{
        schema_version = "1.0"
        summary_type = "controlled_feishu_readback_summary"
        job_id = $JobId
        job_type = $JobType
        status = "failed"
        operation = $Operation
        dry_run = (-not ($RealWrite -and $Readback))
        readback_enabled = $false
        real_readback_allowed = $false
        record_id_present = [bool]$FeishuRecordId
        expected_field_count = 0
        actual_field_count = 0
        matched_field_count = 0
        mismatched_field_count = 0
        missing_field_count = 0
        extra_field_count = 0
        check_passed = $false
        check_path = $CheckPath
        summary_path = $SummaryPath
        error_code = $ErrorCode
        error_message = $ErrorMessage
    }
    Write-JsonFile -Path $RequestPath -Value $RequestDoc
    Write-JsonFile -Path $ExpectedPath -Value $expected
    Write-JsonFile -Path $ActualPath -Value $actual
    Write-JsonFile -Path $CheckPath -Value $check
    Write-JsonFile -Path $SummaryPath -Value $summary
    Write-Error $ErrorMessage
    exit 1
}

$WorkerRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$OutputDir = Join-Path $WorkerRoot ".local_rpa_queue\feishu_readback\$JobType\$JobId"
$RequestPath = Join-Path $OutputDir "feishu_readback_request.json"
$ExpectedPath = Join-Path $OutputDir "feishu_readback_expected.json"
$ActualPath = Join-Path $OutputDir "feishu_readback_actual.json"
$CheckPath = Join-Path $OutputDir "feishu_readback_check.json"
$SummaryPath = Join-Path $OutputDir "feishu_readback_summary.json"
$DryRun = -not ($RealWrite -and $Readback)
$Timestamp = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
$Marker = "XHS_SMOKE Task45 $Timestamp $JobId"

$requestDoc = [ordered]@{
    schema_version = "1.0"
    smoke_type = "feishu_controlled_real_write_readback_smoke"
    job_type = $JobType
    job_id = $JobId
    account_id = $AccountId
    operation = $Operation
    dry_run = $DryRun
    real_write_requested = [bool]$RealWrite
    readback_requested = [bool]$Readback
    marker = "XHS_SMOKE"
    created_at = $Timestamp
    output_dir = $OutputDir
}

if (-not (Test-LocalBaseUrl -Value $BaseUrl)) {
    Write-Failure -RequestDoc $requestDoc -ErrorCode "FEISHU_READBACK_DISABLED" -ErrorMessage "BaseUrl must be local browser-worker API."
}

if ($Operation -eq "update" -and [string]::IsNullOrWhiteSpace($FeishuRecordId)) {
    Write-Failure -RequestDoc $requestDoc -ErrorCode "FEISHU_READBACK_RECORD_ID_REQUIRED" -ErrorMessage "FeishuRecordId is required for update readback smoke."
}

if ($Operation -eq "readback" -and ([string]::IsNullOrWhiteSpace($FeishuRecordId) -or -not $Readback)) {
    Write-Failure -RequestDoc $requestDoc -ErrorCode "FEISHU_READBACK_RECORD_ID_REQUIRED" -ErrorMessage "Readback-only smoke requires -Readback and FeishuRecordId."
}

if ($RealWrite -and -not $Readback) {
    Write-Failure -RequestDoc $requestDoc -ErrorCode "FEISHU_READBACK_DISABLED" -ErrorMessage "Real write readback smoke requires both -RealWrite and -Readback."
}

if ($RealWrite -and $Readback) {
    if ($env:XHS_FEISHU_WRITE_ENABLED -ne "true" -or $env:XHS_ALLOW_REAL_FEISHU_WRITE -ne "true" -or $env:XHS_FEISHU_SMOKE_ENABLED -ne "true" -or $env:XHS_FEISHU_READBACK_ENABLED -ne "true") {
        Write-Failure -RequestDoc $requestDoc -ErrorCode "FEISHU_READBACK_DISABLED" -ErrorMessage "Real Feishu readback smoke requires explicit write, smoke, and readback environment flags."
    }
}

if ($JobType -eq "search") {
    $record = [ordered]@{
        job_id = $JobId
        account_id = $AccountId
        provider_type = "kuaijingvs_yingdao_rpa"
        keyword = "XHS_SMOKE Task45 keyword"
        rank = 1
        title = $Marker
        author = "XHS_SMOKE"
        note_id = "XHS_SMOKE-$JobId"
        note_url = ""
        metric_raw_text = "XHS_SMOKE"
        like_count_text = "0"
        status = "XHS_SMOKE Task45 readback smoke"
        error_code = $null
        error_message = $null
        captured_at = $Timestamp
    }
} else {
    $record = [ordered]@{
        job_id = $JobId
        account_id = $AccountId
        provider_type = "kuaijingvs_yingdao_rpa"
        title = "XHS_SMOKE Task45 $JobId"
        body = "XHS_SMOKE Task45 controlled readback smoke body $Timestamp"
        tags = @("XHS_SMOKE", "Task45")
        status = "XHS_SMOKE Task45 readback smoke"
        note_url = ""
        error_code = $null
        error_message = $null
        updated_at = $Timestamp
    }
}

$payloadJson = (@{ records = @($record) } | ConvertTo-Json -Depth 20)
if ($payloadJson -notmatch "XHS_SMOKE") {
    Write-Failure -RequestDoc $requestDoc -ErrorCode "FEISHU_READBACK_MARKER_REQUIRED" -ErrorMessage "Smoke payload must contain XHS_SMOKE marker."
}

Write-JsonFile -Path $RequestPath -Value $requestDoc

$recordId = if ($FeishuRecordId) { $FeishuRecordId } else { $null }

if ($Operation -ne "readback") {
    $writeBody = [ordered]@{
        job_id = $JobId
        account_id = $AccountId
        operation = $Operation
        feishu_record_id = if ($FeishuRecordId) { $FeishuRecordId } else { $null }
        records = @($record)
        dry_run = $DryRun
    }
    $writePayload = $writeBody | ConvertTo-Json -Depth 20
    $writeResult = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/workflows/xhs/feishu-write/$JobType" -ContentType "application/json" -Body ([System.Text.Encoding]::UTF8.GetBytes($writePayload))
    if ($writeResult.record_id) {
        $recordId = $writeResult.record_id
    }
}

if ($Operation -eq "readback" -or $Readback) {
    if (-not $DryRun -and [string]::IsNullOrWhiteSpace($recordId)) {
        Write-Failure -RequestDoc $requestDoc -ErrorCode "FEISHU_READBACK_RECORD_ID_REQUIRED" -ErrorMessage "Real readback requires a record id from create/update or FeishuRecordId."
    }
    $readbackBody = [ordered]@{
        job_id = $JobId
        account_id = $AccountId
        operation = $Operation
        feishu_record_id = $recordId
        records = @($record)
        dry_run = $DryRun
    }
    $readbackPayload = $readbackBody | ConvertTo-Json -Depth 20
    $readbackResult = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/workflows/xhs/feishu-readback/$JobType" -ContentType "application/json" -Body ([System.Text.Encoding]::UTF8.GetBytes($readbackPayload))
} else {
    $readbackResult = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/workflows/xhs/feishu-readback/$JobType" -ContentType "application/json" -Body ([System.Text.Encoding]::UTF8.GetBytes((@{
        job_id = $JobId
        account_id = $AccountId
        operation = $Operation
        feishu_record_id = $recordId
        records = @($record)
        dry_run = $true
    } | ConvertTo-Json -Depth 20)))
}

Write-Host "Feishu write readback smoke completed."
Write-Host "status=$($readbackResult.status)"
Write-Host "dry_run=$DryRun"
Write-Host "check_passed=$($readbackResult.check_passed)"
Write-Host "expected_path=$($readbackResult.expected_path)"
Write-Host "actual_path=$($readbackResult.actual_path)"
Write-Host "check_path=$($readbackResult.check_path)"
Write-Host "summary_path=$($readbackResult.summary_path)"

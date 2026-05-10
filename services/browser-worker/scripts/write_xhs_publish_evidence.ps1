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
    [string]$EvidenceDir,

    [string]$Status = "success",
    [string]$NoteUrl = "",
    [string]$NoteId = ""
)

$ErrorActionPreference = "Stop"
$dir = New-Item -ItemType Directory -Force -Path $EvidenceDir
$evidencePath = Join-Path $dir.FullName "publish_evidence.json"
$beforePath = Join-Path $dir.FullName "publish_before.png"
$formPath = Join-Path $dir.FullName "publish_form_filled.png"
$resultPath = Join-Path $dir.FullName "publish_result.png"

$payload = [ordered]@{
    job_id = $JobId
    task_type = "xhs_publish_note"
    status = $Status
    account_id = $AccountId
    provider_type = $ProviderType
    title = $Title
    note_url = if ($NoteUrl) { $NoteUrl } else { $null }
    note_id = if ($NoteId) { $NoteId } else { $null }
    published_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    evidence_json_path = $evidencePath
    screenshot_path = $resultPath
    before_publish_screenshot_path = $beforePath
    form_filled_screenshot_path = $formPath
    result_screenshot_path = $resultPath
    error_code = $null
    error_message = $null
}

$json = $payload | ConvertTo-Json -Depth 8
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($evidencePath, $json, $utf8NoBom)
Write-Output $evidencePath

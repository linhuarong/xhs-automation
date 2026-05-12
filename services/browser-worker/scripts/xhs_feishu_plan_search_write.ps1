param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [Parameter(Mandatory=$true)][string]$JobId,
    [string]$AccountId = "",
    [string]$SourceResultPath = "",
    [switch]$DryRun
)

$payload = @{
    job_id = $JobId
    account_id = if ($AccountId) { $AccountId } else { $null }
    operation = "upsert_plan_only"
    source_result_path = if ($SourceResultPath) { $SourceResultPath } else { $null }
    dry_run = $true
} | ConvertTo-Json -Depth 10

$result = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/workflows/xhs/feishu-write/search" -ContentType "application/json" -Body ([System.Text.Encoding]::UTF8.GetBytes($payload))

Write-Host "Feishu search write dry-run completed."
Write-Host "plan_path=$($result.plan_path)"
Write-Host "payload_path=$($result.payload_path)"
Write-Host "result_path=$($result.result_path)"
Write-Host "summary_path=$($result.summary_path)"
Write-Host "written_count=$($result.written_count)"

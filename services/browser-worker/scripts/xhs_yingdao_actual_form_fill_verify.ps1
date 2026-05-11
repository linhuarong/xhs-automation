param(
  [ValidateSet("search", "publish")]
  [string]$JobType = "search",
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [Parameter(Mandatory = $true)]
  [string]$JobId
)

$ErrorActionPreference = "Stop"

$endpoint = "$BaseUrl/api/workflows/xhs/yingdao/actual-form-fill/$JobType/$JobId/verify"
$result = Invoke-RestMethod -Method Get -Uri $endpoint

Write-Host "status: $($result.status)"
Write-Host "trace_valid: $($result.summary.trace_valid)"
Write-Host "result_valid: $($result.summary.result_valid)"
Write-Host "opened_local_html: $($result.summary.opened_local_html)"
Write-Host "opened_external_url: $($result.summary.opened_external_url)"
Write-Host "opened_xhs: $($result.summary.opened_xhs)"
Write-Host "called_external_api: $($result.summary.called_external_api)"
Write-Host "clicked_real_publish: $($result.summary.clicked_real_publish)"

if ($result.status -eq "failed") {
  Write-Host "error_code: $($result.error_code)"
  Write-Host "error_message: $($result.error_message)"
  exit 1
}

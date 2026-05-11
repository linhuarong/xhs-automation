param(
  [ValidateSet("search", "publish")]
  [string]$JobType = "search",
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [Parameter(Mandatory = $true)]
  [string]$JobId
)

$ErrorActionPreference = "Stop"

$endpoint = "$BaseUrl/api/workflows/xhs/account-binding/$JobType/$JobId/verify"
$result = Invoke-RestMethod -Method Get -Uri $endpoint

Write-Host "status: $($result.status)"
Write-Host "binding_status: $($result.summary.binding_status)"
Write-Host "confirmation_valid: $($result.summary.confirmation_valid)"
Write-Host "account_id: $($result.summary.account_id)"
Write-Host "shop_id: $($result.summary.shop_id)"
Write-Host "opened_shop: $($result.summary.opened_shop)"
Write-Host "opened_xhs: $($result.summary.opened_xhs)"
Write-Host "called_yingdao_openapi: $($result.summary.called_yingdao_openapi)"
Write-Host "called_kuaijingvs_open_shop: $($result.summary.called_kuaijingvs_open_shop)"

if ($result.status -eq "failed") {
  Write-Host "error_code: $($result.error_code)"
  Write-Host "error_message: $($result.error_message)"
  exit 1
}

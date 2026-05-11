param(
  [ValidateSet("search", "publish")]
  [string]$JobType = "search",
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [Parameter(Mandatory = $true)]
  [string]$JobId,
  [string]$Status = "success"
)

$ErrorActionPreference = "Stop"

$endpoint = "$BaseUrl/api/workflows/xhs/account-binding/$JobType/$JobId/mock-confirm"
$payload = @{ status = $Status }
$json = $payload | ConvertTo-Json -Depth 5
$result = Invoke-RestMethod -Method Post -Uri $endpoint -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($json))

Write-Host "status: $($result.status)"
Write-Host "confirmation_path: $($result.confirmation_path)"
Write-Host "message: $($result.message)"

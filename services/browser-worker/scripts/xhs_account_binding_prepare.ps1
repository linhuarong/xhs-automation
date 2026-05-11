param(
  [ValidateSet("search", "publish")]
  [string]$JobType = "search",
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [Parameter(Mandatory = $true)]
  [string]$JobId,
  [Parameter(Mandatory = $true)]
  [string]$AccountId,
  [string]$Keyword = "",
  [int]$Limit = 20,
  [string]$Title = "",
  [string]$Body = "",
  [string]$Tags = "",
  [string]$ImagePaths = "",
  [string]$PublishMode = "manual_review"
)

$ErrorActionPreference = "Stop"

# Safety boundary: this helper only calls browser-worker local account-binding APIs.
# It does not open shop, close shop, open Xiaohongshu, or call Yingdao OpenAPI.

if ($JobType -eq "search") {
  $endpoint = "$BaseUrl/api/workflows/xhs/account-binding/search/prepare"
  $payload = @{
    job_id = $JobId
    account_id = $AccountId
    keyword = $Keyword
    limit = $Limit
  }
} else {
  $endpoint = "$BaseUrl/api/workflows/xhs/account-binding/publish/prepare"
  $tagList = @()
  if ($Tags.Trim().Length -gt 0) {
    $tagList = $Tags.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
  }
  $imageList = @()
  if ($ImagePaths.Trim().Length -gt 0) {
    $imageList = $ImagePaths.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
  }
  $payload = @{
    job_id = $JobId
    account_id = $AccountId
    title = $Title
    body = $Body
    tags = $tagList
    image_paths = $imageList
    publish_mode = $PublishMode
  }
}

$json = $payload | ConvertTo-Json -Depth 10
$result = Invoke-RestMethod -Method Post -Uri $endpoint -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($json))

Write-Host "status: $($result.status)"
Write-Host "binding_status: $($result.binding_status)"
Write-Host "account_binding_context_path: $($result.account_binding_context_path)"
Write-Host "actual_form_fill_input_path: $($result.actual_form_fill_input_path)"
Write-Host "confirmation_path: $($result.confirmation_path)"
if ($result.error_code) {
  Write-Host "error_code: $($result.error_code)"
  Write-Host "error_message: $($result.error_message)"
}

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

if ($JobType -eq "search") {
  $endpoint = "$BaseUrl/api/workflows/xhs/yingdao/actual-form-fill/search/prepare"
  $payload = @{
    job_id = $JobId
    account_id = $AccountId
    keyword = $Keyword
    limit = $Limit
  }
} else {
  $endpoint = "$BaseUrl/api/workflows/xhs/yingdao/actual-form-fill/publish/prepare"
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
Write-Host "html_uri: $($result.html_uri)"
Write-Host "actual_form_fill_input_path: $($result.actual_form_fill_input_path)"
Write-Host "runbook_path: $($result.actual_form_fill_runbook_path)"
Write-Host "expected_trace_path: $($result.expected_trace_path)"
Write-Host "expected_result_path: $($result.expected_result_path)"

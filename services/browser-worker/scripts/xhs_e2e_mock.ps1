param(
    [Parameter(Mandatory = $true)]
    [string]$WorkflowId,

    [Parameter(Mandatory = $true)]
    [string]$AccountId,

    [Parameter(Mandatory = $true)]
    [string]$Keywords,

    [int]$Limit = 20,
    [int]$MaxPublishJobs = 1,
    [string]$ApiBaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$keywordList = $Keywords.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
$body = @{
    workflow_id = $WorkflowId
    account_id = $AccountId
    search_provider_type = "mock"
    publish_provider_type = "mock"
    keywords = @($keywordList)
    limit = $Limit
    max_publish_jobs = $MaxPublishJobs
    mode = "mock"
} | ConvertTo-Json -Depth 8

Invoke-RestMethod `
    -Method Post `
    -Uri "$ApiBaseUrl/api/xhs/workflows/search-to-publish/mock" `
    -ContentType "application/json; charset=utf-8" `
    -Body $body

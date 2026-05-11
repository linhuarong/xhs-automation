param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$result = Invoke-RestMethod `
    -Method Get `
    -Uri "$BaseUrl/api/workflows/xhs/external-readiness"

Write-Output "status: $($result.status)"
Write-Output "safe_mode: $($result.safe_mode)"
Write-Output "environment: $($result.environment)"
Write-Output "summary: total=$($result.summary.total), ready=$($result.summary.ready), mock_ready=$($result.summary.mock_ready), disabled=$($result.summary.disabled), missing_config=$($result.summary.missing_config), failed=$($result.summary.failed)"

foreach ($dependency in $result.dependencies) {
    Write-Output "$($dependency.name): status=$($dependency.status), mode=$($dependency.mode), message=$($dependency.message)"
}

if ($result.status -eq "failed") {
    exit 1
}

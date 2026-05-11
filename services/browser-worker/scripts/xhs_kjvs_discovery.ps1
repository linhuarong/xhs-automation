param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
try {
    $result = Invoke-RestMethod `
        -Method Get `
        -Uri "$BaseUrl/api/workflows/xhs/kuaijingvs/discovery"
}
catch {
    $body = $null
    if ($_.ErrorDetails.Message) {
        try {
            $body = $_.ErrorDetails.Message | ConvertFrom-Json
        }
        catch {
            $body = $null
        }
    }
    if ($body -and $body.error_code -eq "XHS_EXTERNAL_LIVE_CHECK_DISABLED") {
        Write-Output "KuaJingVS live readonly discovery is disabled."
        Write-Output "Please set XHS_ALLOW_LIVE_READONLY_CHECKS=true and restart browser-worker."
        exit 1
    }
    throw
}

if ($result.status -eq "blocked" -or $result.error_code -eq "XHS_EXTERNAL_LIVE_CHECK_DISABLED") {
    Write-Output "KuaJingVS live readonly discovery is disabled."
    Write-Output "Please set XHS_ALLOW_LIVE_READONLY_CHECKS=true and restart browser-worker."
    exit 1
}

Write-Output "status: $($result.status)"
Write-Output "mode: $($result.mode)"
Write-Output "shop_count: $($result.shop_count)"
Write-Output "profile_map_valid: $($result.profile_map_valid)"
Write-Output "matched_account_count: $($result.matched_account_count)"
Write-Output "unmatched_account_count: $($result.unmatched_account_count)"
Write-Output "evidence_json_path: $($result.evidence_json_path)"

if ($result.unmatched_accounts) {
    Write-Output "unmatched_accounts:"
    $result.unmatched_accounts | ConvertTo-Json -Depth 8
}

if ($result.status -ne "success") {
    exit 1
}

param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$SourceEvidencePath = ".local_evidence\kuaijingvs_discovery\discovery.json"
)

$ErrorActionPreference = "Stop"

# Local-only hardening helper. It does not call KuaJingVS API and does not open shop.

$endpoint = "$BaseUrl/api/workflows/xhs/kuaijingvs/discovery/harden"
$payload = @{
  source_evidence_path = $SourceEvidencePath
}
$json = $payload | ConvertTo-Json -Depth 10
$result = Invoke-RestMethod -Method Post -Uri $endpoint -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($json))

Write-Host "status: $($result.status)"
Write-Host "hardened_evidence_path: $($result.hardened_evidence_path)"
Write-Host "summary_path: $($result.summary_path)"
Write-Host "shop_count: $($result.shop_count)"
Write-Host "sensitive_value_scan_passed: $($result.sensitive_value_scan_passed)"
Write-Host "evidence_hash: $($result.evidence_hash)"
if ($result.error_code) {
  Write-Host "error_code: $($result.error_code)"
  Write-Host "error_message: $($result.error_message)"
  exit 1
}

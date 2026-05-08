param(
  [string]$JobId = "yingdao-smoke-1",
  [string]$Keyword = "眼影",
  [string]$AccountId = "xhs_dev_01",
  [string]$ProviderType = "kuaijingvs_yingdao_rpa",
  [string]$EvidenceDir = "G:\AI-Automation\xhs-automation\services\browser-worker\.local_evidence\yingdao-smoke-1"
)

if (!(Test-Path $EvidenceDir)) {
  New-Item -ItemType Directory -Force $EvidenceDir | Out-Null
}

$screenshotPath = Join-Path $EvidenceDir "xhs_search_smoke.png"
$evidencePath = Join-Path $EvidenceDir "search_evidence.json"

$data = [ordered]@{
  job_id = $JobId
  task_type = "xhs_keyword_search"
  status = "success"
  keyword = $Keyword
  account_id = $AccountId
  provider_type = $ProviderType
  captured_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
  screenshot_path = $screenshotPath
  evidence_json_path = $evidencePath
  item_count = 0
  normalized_record_count = 0
  result_area_found = $true
  items = @()
  normalized_records = @()
}

$data | ConvertTo-Json -Depth 10 | Set-Content -Encoding utf8 $evidencePath

Write-Host "Evidence written to: $evidencePath"

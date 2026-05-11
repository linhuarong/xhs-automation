param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$SchemaPath = "database\xhs_persistence_schema.sql"
)

$ErrorActionPreference = "Stop"

if ($BaseUrl -notmatch '^http://(127\.0\.0\.1|localhost)(:\d+)?$') {
  Write-Error "BaseUrl must point to local browser-worker only."
  exit 1
}

if (-not (Test-Path -LiteralPath $SchemaPath)) {
  Write-Error "Schema file not found: $SchemaPath"
  exit 1
}

$health = Invoke-RestMethod -Method Get -Uri "$BaseUrl/health"
$readiness = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/workflows/xhs/external-readiness"

[PSCustomObject]@{
  schema_path = $SchemaPath
  schema_exists = $true
  dry_run = $true
  health_status = $health.status
  readiness_status = $readiness.status
} | ConvertTo-Json -Depth 8

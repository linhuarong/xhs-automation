param(
  [string]$Dsn = "",
  [string]$SchemaPath = "database\xhs_persistence_schema.sql",
  [switch]$ConfirmApply
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $SchemaPath)) {
  Write-Error "Schema file not found: $SchemaPath"
  exit 1
}

if (-not $ConfirmApply) {
  [PSCustomObject]@{
    dry_run = $true
    schema_path = $SchemaPath
    message = "No schema was applied. Re-run with -ConfirmApply and a local DSN to execute psql."
  } | ConvertTo-Json -Depth 5
  exit 0
}

if ([string]::IsNullOrWhiteSpace($Dsn)) {
  Write-Error "Dsn is required when -ConfirmApply is used."
  exit 1
}

if ($Dsn -notmatch '^postgresql://[^@]+@127\.0\.0\.1:\d+/' -and $Dsn -notmatch '^postgresql://[^@]+@localhost:\d+/') {
  Write-Error "Only local PostgreSQL DSNs are allowed by this helper."
  exit 1
}

psql $Dsn -f $SchemaPath

param(
    [Parameter(Mandatory = $true)]
    [string]$EvidenceJsonPath,

    [switch]$WriteBack
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$WorkerRoot = Resolve-Path (Join-Path $ScriptDir "..")
$PythonPath = Join-Path $WorkerRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonPath)) {
    $PythonPath = "python"
}

$code = @'
import json
import sys
from app.services.xhs_evidence_service import XhsEvidenceService

path = sys.argv[1]
write_back = sys.argv[2].lower() == "true"
service = XhsEvidenceService()
evidence = service.read_evidence(path)
if write_back:
    evidence = service.write_normalized_evidence(evidence, path)
print(json.dumps({
    "status": "success",
    "normalized_record_count": evidence.normalized_record_count or 0,
}, ensure_ascii=False))
'@

Push-Location $WorkerRoot
try {
    & $PythonPath -c $code $EvidenceJsonPath ([bool]$WriteBack).ToString().ToLower()
}
finally {
    Pop-Location
}

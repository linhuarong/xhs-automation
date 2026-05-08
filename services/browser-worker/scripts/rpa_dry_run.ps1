param(
    [Parameter(Mandatory = $true)]
    [string]$JobId,

    [Parameter(Mandatory = $true)]
    [string]$AccountId,

    [Parameter(Mandatory = $true)]
    [string]$Keyword,

    [string]$ProviderType = "kuaijingvs_yingdao_rpa"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$WorkerRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $WorkerRoot

$PythonPath = Join-Path $WorkerRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonPath)) {
    $PythonPath = "python"
}

$PythonCode = @'
import json
import sys

from app.schemas.search_job import SearchJob
from app.services.rpa_dry_run import RpaDryRunService

job = SearchJob(
    job_id=sys.argv[1],
    account_id=sys.argv[2],
    keyword=sys.argv[3],
    provider_type=sys.argv[4],
)
report = RpaDryRunService().check_search_job(job)
print(json.dumps(report, ensure_ascii=False, indent=2))
sys.exit(0 if report.get("status") == "success" else 1)
'@

& $PythonPath -c $PythonCode $JobId $AccountId $Keyword $ProviderType
exit $LASTEXITCODE

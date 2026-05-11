from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"


def test_e2e_mock_script_contract() -> None:
    script = (SCRIPT_ROOT / "xhs_e2e_mock.ps1").read_text(encoding="utf-8")

    assert "WorkflowId" in script
    assert "AccountId" in script
    assert "Keywords" in script
    assert "/api/xhs/workflows/search-to-publish/mock" in script


def test_health_check_script_contract() -> None:
    script = (SCRIPT_ROOT / "xhs_health_check.ps1").read_text(encoding="utf-8")

    assert "/api/workflows/xhs/health" in script


def test_job_status_script_contract() -> None:
    script = (SCRIPT_ROOT / "xhs_job_status.ps1").read_text(encoding="utf-8")

    assert "JobId" in script
    assert "JobType" in script
    assert "/api/webhooks/openclaw/xhs/job-status" in script

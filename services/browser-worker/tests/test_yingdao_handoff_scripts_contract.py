from pathlib import Path


SCRIPTS_ROOT = Path(__file__).resolve().parents[1] / "scripts"


def test_yingdao_handoff_scripts_exist() -> None:
    expected = [
        "xhs_yingdao_prepare_search_handoff.ps1",
        "xhs_yingdao_prepare_publish_handoff.ps1",
        "xhs_yingdao_check_active_job.ps1",
        "xhs_yingdao_mock_evidence.ps1",
    ]

    for script_name in expected:
        assert (SCRIPTS_ROOT / script_name).exists()


def test_prepare_search_script_contract() -> None:
    content = (SCRIPTS_ROOT / "xhs_yingdao_prepare_search_handoff.ps1").read_text(encoding="utf-8")

    assert "BaseUrl" in content
    assert "/api/workflows/xhs/yingdao/local-handoff/search" in content
    assert "Invoke-RestMethod" in content


def test_prepare_publish_script_contract() -> None:
    content = (SCRIPTS_ROOT / "xhs_yingdao_prepare_publish_handoff.ps1").read_text(encoding="utf-8")

    assert "BaseUrl" in content
    assert "/api/workflows/xhs/yingdao/local-handoff/publish" in content
    assert "manual_review" in content


def test_mock_evidence_script_is_local_only() -> None:
    content = (SCRIPTS_ROOT / "xhs_yingdao_mock_evidence.ps1").read_text(encoding="utf-8")

    assert "Invoke-RestMethod" not in content
    assert "http://" not in content
    assert "https://" not in content
    assert "search_evidence.json" in content
    assert "publish_evidence.json" in content

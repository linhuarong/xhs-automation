from pathlib import Path


SCRIPTS_ROOT = Path(__file__).resolve().parents[1] / "scripts"


def test_form_simulator_scripts_and_runbook_exist() -> None:
    for name in [
        "xhs_yingdao_form_sim_prepare.ps1",
        "xhs_yingdao_form_sim_verify.ps1",
        "xhs_yingdao_form_sim_mock_write.ps1",
        "xhs_yingdao_form_sim_runbook.txt",
    ]:
        assert (SCRIPTS_ROOT / name).exists()


def test_prepare_script_contract() -> None:
    content = (SCRIPTS_ROOT / "xhs_yingdao_form_sim_prepare.ps1").read_text(encoding="utf-8")

    assert "BaseUrl" in content
    assert "/api/workflows/xhs/yingdao/form-simulator/search/prepare" in content
    assert "/api/workflows/xhs/yingdao/form-simulator/publish/prepare" in content
    assert "Browserless simulator only" in content


def test_verify_script_contract() -> None:
    content = (SCRIPTS_ROOT / "xhs_yingdao_form_sim_verify.ps1").read_text(encoding="utf-8")

    assert "BaseUrl" in content
    assert "/api/workflows/xhs/yingdao/form-simulator/$JobType/$JobId/verify" in content
    assert "trace_valid" in content
    assert "clicked_real_publish" in content


def test_mock_write_script_contract_is_local_only() -> None:
    content = (SCRIPTS_ROOT / "xhs_yingdao_form_sim_mock_write.ps1").read_text(encoding="utf-8")

    assert "/api/workflows/xhs/yingdao/form-simulator/$JobType/$JobId/mock-write" in content
    assert "No browser" in content
    assert "local HTML" in content
    assert "Xiaohongshu" in content


def test_runbook_contains_forbidden_actions() -> None:
    content = (SCRIPTS_ROOT / "xhs_yingdao_form_sim_runbook.txt").read_text(encoding="utf-8")

    assert "Do not open browser" in content
    assert "Do not open local HTML" in content
    assert "Do not open Xiaohongshu" in content
    assert "Do not click publish" in content
    assert "Do not call Yingdao cloud OpenAPI" in content

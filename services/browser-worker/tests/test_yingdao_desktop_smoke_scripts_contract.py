from pathlib import Path


SCRIPTS_ROOT = Path(__file__).resolve().parents[1] / "scripts"


def test_desktop_smoke_scripts_and_runbook_exist() -> None:
    for name in [
        "xhs_yingdao_desktop_smoke_prepare.ps1",
        "xhs_yingdao_desktop_smoke_verify.ps1",
        "xhs_yingdao_desktop_smoke_mock_write.ps1",
        "xhs_yingdao_desktop_smoke_runbook.txt",
    ]:
        assert (SCRIPTS_ROOT / name).exists()


def test_prepare_script_contract() -> None:
    content = (SCRIPTS_ROOT / "xhs_yingdao_desktop_smoke_prepare.ps1").read_text(encoding="utf-8")

    assert "BaseUrl" in content
    assert "/api/workflows/xhs/yingdao/desktop-smoke/search/prepare" in content
    assert "/api/workflows/xhs/yingdao/desktop-smoke/publish/prepare" in content


def test_verify_script_contract() -> None:
    content = (SCRIPTS_ROOT / "xhs_yingdao_desktop_smoke_verify.ps1").read_text(encoding="utf-8")

    assert "BaseUrl" in content
    assert "/api/workflows/xhs/yingdao/desktop-smoke/$JobType/$JobId/verify" in content
    assert "opened_browser" in content
    assert "opened_xhs" in content


def test_mock_write_script_contract_is_local_browserless() -> None:
    content = (SCRIPTS_ROOT / "xhs_yingdao_desktop_smoke_mock_write.ps1").read_text(encoding="utf-8")

    assert "/api/workflows/xhs/yingdao/desktop-smoke/$JobType/$JobId/mock-write" in content
    assert "No Yingdao OpenAPI" in content
    assert "browser" in content
    assert "XHS" in content


def test_runbook_contains_forbidden_actions() -> None:
    content = (SCRIPTS_ROOT / "xhs_yingdao_desktop_smoke_runbook.txt").read_text(encoding="utf-8")

    assert "Do not open browser" in content
    assert "Do not open Xiaohongshu" in content
    assert "Do not click final publish" in content
    assert "Do not call Yingdao cloud OpenAPI" in content

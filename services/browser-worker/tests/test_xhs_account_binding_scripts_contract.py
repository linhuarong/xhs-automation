from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def test_account_binding_scripts_exist() -> None:
    for name in [
        "xhs_account_binding_prepare.ps1",
        "xhs_account_binding_verify.ps1",
        "xhs_account_binding_mock_confirm.ps1",
        "xhs_account_binding_runbook.txt",
    ]:
        assert (SCRIPTS_DIR / name).exists()


def test_prepare_script_contains_target_endpoints() -> None:
    text = (SCRIPTS_DIR / "xhs_account_binding_prepare.ps1").read_text(encoding="utf-8")

    assert "account-binding/search/prepare" in text
    assert "account-binding/publish/prepare" in text
    assert "BaseUrl" in text
    assert "open shop" in text.lower()


def test_verify_and_mock_confirm_scripts_call_local_api() -> None:
    verify_text = (SCRIPTS_DIR / "xhs_account_binding_verify.ps1").read_text(encoding="utf-8")
    mock_text = (SCRIPTS_DIR / "xhs_account_binding_mock_confirm.ps1").read_text(encoding="utf-8")

    assert "account-binding/$JobType/$JobId/verify" in verify_text
    assert "account-binding/$JobType/$JobId/mock-confirm" in mock_text
    assert "Invoke-RestMethod" in verify_text
    assert "Invoke-RestMethod" in mock_text


def test_runbook_states_safety_boundaries() -> None:
    text = (SCRIPTS_DIR / "xhs_account_binding_runbook.txt").read_text(encoding="utf-8")

    assert "不要 open shop" in text
    assert "不要打开小红书" in text
    assert "不要点击真实发布" in text
    assert "不要调用影刀云 API" in text

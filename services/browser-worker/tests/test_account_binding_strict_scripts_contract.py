from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def test_strict_scripts_exist() -> None:
    for name in [
        "xhs_kjvs_discovery_harden.ps1",
        "xhs_account_binding_strict_check.ps1",
        "xhs_account_binding_strict_runbook.txt",
    ]:
        assert (SCRIPTS_DIR / name).exists()


def test_harden_script_calls_local_endpoint_only() -> None:
    text = (SCRIPTS_DIR / "xhs_kjvs_discovery_harden.ps1").read_text(encoding="utf-8")

    assert "kuaijingvs/discovery/harden" in text
    assert "SourceEvidencePath" in text
    assert "open shop" in text.lower()


def test_strict_check_script_contains_target_endpoints() -> None:
    text = (SCRIPTS_DIR / "xhs_account_binding_strict_check.ps1").read_text(encoding="utf-8")

    assert "account-binding/search/strict-check" in text
    assert "account-binding/publish/strict-check" in text
    assert "BaseUrl" in text
    assert "open shop" in text.lower()


def test_strict_runbook_states_safety_boundaries() -> None:
    text = (SCRIPTS_DIR / "xhs_account_binding_strict_runbook.txt").read_text(encoding="utf-8")

    assert "不要 open shop" in text
    assert "不要打开小红书" in text
    assert "不要点击真实发布" in text

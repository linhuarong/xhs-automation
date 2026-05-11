from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def test_actual_form_fill_scripts_exist() -> None:
    for name in [
        "xhs_yingdao_actual_form_fill_prepare.ps1",
        "xhs_yingdao_actual_form_fill_open.ps1",
        "xhs_yingdao_actual_form_fill_verify.ps1",
        "xhs_yingdao_actual_form_fill_mock_write.ps1",
        "xhs_yingdao_actual_form_fill_runbook.txt",
    ]:
        assert (SCRIPTS_DIR / name).exists()


def test_prepare_script_contains_target_endpoints() -> None:
    text = (SCRIPTS_DIR / "xhs_yingdao_actual_form_fill_prepare.ps1").read_text(encoding="utf-8")

    assert "actual-form-fill/search/prepare" in text
    assert "actual-form-fill/publish/prepare" in text
    assert "BaseUrl" in text


def test_open_script_rejects_unsafe_targets() -> None:
    text = (SCRIPTS_DIR / "xhs_yingdao_actual_form_fill_open.ps1").read_text(encoding="utf-8").lower()

    assert "http://" in text
    assert "https://" in text
    assert "xiaohongshu.com" in text
    assert ".local_rpa_queue" in text
    assert "yingdao" in text
    assert "sandbox" in text


def test_verify_and_mock_write_scripts_call_local_api() -> None:
    verify_text = (SCRIPTS_DIR / "xhs_yingdao_actual_form_fill_verify.ps1").read_text(encoding="utf-8")
    mock_text = (SCRIPTS_DIR / "xhs_yingdao_actual_form_fill_mock_write.ps1").read_text(encoding="utf-8")

    assert "actual-form-fill/$JobType/$JobId/verify" in verify_text
    assert "actual-form-fill/$JobType/$JobId/mock-write" in mock_text


def test_runbook_states_safety_boundaries() -> None:
    text = (SCRIPTS_DIR / "xhs_yingdao_actual_form_fill_runbook.txt").read_text(encoding="utf-8")

    assert "不打开小红书" in text
    assert "不打开外部网页" in text
    assert "不点击真实发布" in text

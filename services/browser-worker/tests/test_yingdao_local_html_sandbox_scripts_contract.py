from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"


def test_html_sandbox_scripts_exist() -> None:
    for name in [
        "xhs_yingdao_html_sandbox_prepare.ps1",
        "xhs_yingdao_html_sandbox_open.ps1",
        "xhs_yingdao_html_sandbox_verify.ps1",
        "xhs_yingdao_html_sandbox_mock_write.ps1",
        "xhs_yingdao_html_sandbox_runbook.txt",
    ]:
        assert (SCRIPT_ROOT / name).exists()


def test_prepare_script_contains_expected_endpoints() -> None:
    text = (SCRIPT_ROOT / "xhs_yingdao_html_sandbox_prepare.ps1").read_text(encoding="utf-8")

    assert "/api/workflows/xhs/yingdao/html-sandbox/search/prepare" in text
    assert "/api/workflows/xhs/yingdao/html-sandbox/publish/prepare" in text
    assert "BaseUrl" in text


def test_open_script_blocks_external_urls_and_xhs() -> None:
    text = (SCRIPT_ROOT / "xhs_yingdao_html_sandbox_open.ps1").read_text(encoding="utf-8")

    assert "http://" in text
    assert "https://" in text
    assert "xiaohongshu.com" in text
    assert ".local_rpa_queue\\yingdao\\sandbox" in text
    assert "Start-Process" in text


def test_verify_and_mock_write_scripts_contain_expected_endpoints() -> None:
    verify = (SCRIPT_ROOT / "xhs_yingdao_html_sandbox_verify.ps1").read_text(encoding="utf-8")
    mock_write = (SCRIPT_ROOT / "xhs_yingdao_html_sandbox_mock_write.ps1").read_text(encoding="utf-8")

    assert "/api/workflows/xhs/yingdao/html-sandbox/$JobType/$JobId/verify" in verify
    assert "/api/workflows/xhs/yingdao/html-sandbox/$JobType/$JobId/mock-write" in mock_write


def test_runbook_safety_language() -> None:
    text = (SCRIPT_ROOT / "xhs_yingdao_html_sandbox_runbook.txt").read_text(encoding="utf-8")

    assert "不打开小红书" in text
    assert "不打开外部网页" in text
    assert "不点击真实发布" in text
    assert "Do not call Yingdao cloud API" in text

from pathlib import Path


SCRIPT_DIR = Path("services/browser-worker/scripts")


def _read(name: str) -> str:
    return (SCRIPT_DIR / name).read_text(encoding="utf-8")


def test_feishu_write_scripts_and_runbook_exist() -> None:
    assert (SCRIPT_DIR / "xhs_feishu_plan_search_write.ps1").exists()
    assert (SCRIPT_DIR / "xhs_feishu_plan_publish_write.ps1").exists()
    assert (SCRIPT_DIR / "xhs_feishu_write_runbook.txt").exists()


def test_feishu_write_scripts_default_to_dry_run_and_local_api() -> None:
    for name in [
        "xhs_feishu_plan_search_write.ps1",
        "xhs_feishu_plan_publish_write.ps1",
    ]:
        content = _read(name)
        assert "127.0.0.1" in content
        assert "dry_run" in content.lower()
        assert "/api/workflows/xhs/feishu-write/" in content
        assert "app_secret" not in content.lower()
        assert "tenant_access_token" not in content.lower()
        assert "open.feishu.cn" not in content.lower()
        assert "xiaohongshu.com" not in content.lower()
        assert "postgresql://" not in content.lower()


def test_feishu_write_runbook_mentions_safety_boundary() -> None:
    content = _read("xhs_feishu_write_runbook.txt")

    assert "dry-run" in content.lower()
    assert "Do not print or copy app secret" in content
    assert "Do not write real Feishu" in content
    assert "Do not open Xiaohongshu" in content
    assert "Do not call Yingdao" in content

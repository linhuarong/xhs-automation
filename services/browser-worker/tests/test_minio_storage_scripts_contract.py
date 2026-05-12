from pathlib import Path


SCRIPT_DIR = Path("services/browser-worker/scripts")


def _read(name: str) -> str:
    return (SCRIPT_DIR / name).read_text(encoding="utf-8")


def test_minio_storage_scripts_and_runbook_exist() -> None:
    assert (SCRIPT_DIR / "xhs_minio_plan_search_upload.ps1").exists()
    assert (SCRIPT_DIR / "xhs_minio_plan_publish_upload.ps1").exists()
    assert (SCRIPT_DIR / "xhs_minio_storage_runbook.txt").exists()


def test_minio_storage_scripts_default_to_dry_run_and_local_api() -> None:
    for name in [
        "xhs_minio_plan_search_upload.ps1",
        "xhs_minio_plan_publish_upload.ps1",
    ]:
        content = _read(name)
        assert "127.0.0.1" in content
        assert "dry_run" in content.lower() or "DryRun" in content
        assert "/api/workflows/xhs/minio-storage/" in content
        assert "access_key" not in content.lower()
        assert "secret_key" not in content.lower()
        assert "feishu.cn" not in content.lower()
        assert "n8n.cloud" not in content.lower()
        assert "openclaw" not in content.lower()
        assert "xiaohongshu.com" not in content.lower()


def test_minio_storage_runbook_mentions_sensitive_file_boundary() -> None:
    content = _read("xhs_minio_storage_runbook.txt")

    assert "dry-run" in content.lower()
    assert "Do not upload .env files" in content
    assert "Do not upload .config files" in content
    assert "Do not open Xiaohongshu" in content
    assert "Do not call Yingdao" in content

from pathlib import Path


SCRIPT_DIR = Path("services/browser-worker/scripts")


def _read(name: str) -> str:
    return (SCRIPT_DIR / name).read_text(encoding="utf-8")


def test_feishu_real_write_smoke_script_and_runbook_exist() -> None:
    assert (SCRIPT_DIR / "xhs_feishu_real_write_smoke.ps1").exists()
    assert (SCRIPT_DIR / "xhs_feishu_real_write_smoke_runbook.txt").exists()


def test_feishu_real_write_smoke_defaults_to_dry_run() -> None:
    content = _read("xhs_feishu_real_write_smoke.ps1")

    assert "[switch]$RealWrite" in content
    assert "$DryRun = -not $RealWrite" in content
    assert "dry_run = $DryRun" in content
    assert "dry_run = $false" not in content.lower()
    assert "127.0.0.1" in content
    assert "/api/workflows/xhs/feishu-write/$JobType" in content


def test_feishu_real_write_requires_all_smoke_gates() -> None:
    content = _read("xhs_feishu_real_write_smoke.ps1")

    assert "$RealWrite" in content
    assert "XHS_FEISHU_WRITE_ENABLED" in content
    assert "XHS_ALLOW_REAL_FEISHU_WRITE" in content
    assert "XHS_FEISHU_SMOKE_ENABLED" in content
    assert "FEISHU_SMOKE_DISABLED" in content


def test_feishu_real_write_update_requires_record_id() -> None:
    content = _read("xhs_feishu_real_write_smoke.ps1")

    assert 'Operation -eq "update"' in content
    assert "FeishuRecordId" in content
    assert "FEISHU_SMOKE_RECORD_ID_REQUIRED" in content


def test_feishu_real_write_smoke_payload_has_marker_and_local_outputs() -> None:
    content = _read("xhs_feishu_real_write_smoke.ps1")

    assert "XHS_SMOKE" in content
    assert "Task44" in content
    assert ".local_rpa_queue\\feishu_smoke\\$JobType\\$JobId" in content
    assert "feishu_smoke_request.json" in content
    assert "feishu_smoke_result.json" in content
    assert "feishu_smoke_summary.json" in content


def test_feishu_real_write_smoke_script_does_not_expose_sensitive_values() -> None:
    content = _read("xhs_feishu_real_write_smoke.ps1").lower()

    assert "app_secret" not in content
    assert "tenant_access_token" not in content
    assert "user_access_token" not in content
    assert "app_token" not in content
    assert "table_id" not in content
    assert "open.feishu.cn" not in content
    assert "xiaohongshu.com" not in content
    assert "postgresql://" not in content
    assert "minio" not in content


def test_feishu_real_write_smoke_runbook_mentions_manual_safety() -> None:
    content = _read("xhs_feishu_real_write_smoke_runbook.txt")

    assert "dry-run" in content.lower()
    assert "XHS_SMOKE" in content
    assert "XHS_FEISHU_SMOKE_ENABLED=true" in content
    assert "Do not write batches to real Feishu" in content
    assert "Do not open Xiaohongshu" in content
    assert "Do not call Yingdao" in content
    assert "Do not open shop" in content

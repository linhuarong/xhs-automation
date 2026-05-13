from pathlib import Path


SCRIPT_DIR = Path("services/browser-worker/scripts")


def _read(name: str) -> str:
    return (SCRIPT_DIR / name).read_text(encoding="utf-8")


def test_feishu_readback_smoke_script_and_runbook_exist() -> None:
    assert (SCRIPT_DIR / "xhs_feishu_real_write_readback_smoke.ps1").exists()
    assert (SCRIPT_DIR / "xhs_feishu_real_write_readback_smoke_runbook.txt").exists()


def test_feishu_readback_smoke_defaults_to_dry_run_and_local_api() -> None:
    content = _read("xhs_feishu_real_write_readback_smoke.ps1")

    assert "[switch]$RealWrite" in content
    assert "[switch]$Readback" in content
    assert "$DryRun = -not ($RealWrite -and $Readback)" in content
    assert "127.0.0.1" in content
    assert "/api/workflows/xhs/feishu-readback/$JobType" in content
    assert "dry_run = $false" not in content.lower()


def test_feishu_readback_real_path_requires_four_env_flags() -> None:
    content = _read("xhs_feishu_real_write_readback_smoke.ps1")

    assert "XHS_FEISHU_WRITE_ENABLED" in content
    assert "XHS_ALLOW_REAL_FEISHU_WRITE" in content
    assert "XHS_FEISHU_SMOKE_ENABLED" in content
    assert "XHS_FEISHU_READBACK_ENABLED" in content
    assert "-RealWrite and -Readback" in content


def test_feishu_readback_script_requires_record_id_for_readback_and_update() -> None:
    content = _read("xhs_feishu_real_write_readback_smoke.ps1")

    assert 'Operation -eq "update"' in content
    assert 'Operation -eq "readback"' in content
    assert "FeishuRecordId" in content
    assert "FEISHU_READBACK_RECORD_ID_REQUIRED" in content


def test_feishu_readback_script_has_marker_and_output_contract() -> None:
    content = _read("xhs_feishu_real_write_readback_smoke.ps1")

    assert "XHS_SMOKE" in content
    assert "Task45" in content
    assert ".local_rpa_queue\\feishu_readback\\$JobType\\$JobId" in content
    assert "feishu_readback_request.json" in content
    assert "feishu_readback_expected.json" in content
    assert "feishu_readback_actual.json" in content
    assert "feishu_readback_check.json" in content
    assert "feishu_readback_summary.json" in content


def test_feishu_readback_script_does_not_expose_sensitive_values_or_batch_ops() -> None:
    content = _read("xhs_feishu_real_write_readback_smoke.ps1").lower()

    assert "app_secret" not in content
    assert "tenant_access_token" not in content
    assert "app_token" not in content
    assert "table_id" not in content
    assert "open.feishu.cn" not in content
    assert "xiaohongshu.com" not in content
    assert "delete" not in content
    assert "batch" not in content


def test_feishu_readback_runbook_mentions_safety_boundary() -> None:
    content = _read("xhs_feishu_real_write_readback_smoke_runbook.txt")

    assert "dry-run" in content.lower()
    assert "XHS_SMOKE" in content
    assert "XHS_FEISHU_READBACK_ENABLED=true" in content
    assert "Do not list records" in content
    assert "Do not delete records" in content
    assert "Do not call Xiaohongshu" in content
    assert "Do not call Yingdao" in content

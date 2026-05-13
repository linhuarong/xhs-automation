from pathlib import Path


SCRIPT_DIR = Path("services/browser-worker/scripts")


def _read(name: str) -> str:
    return (SCRIPT_DIR / name).read_text(encoding="utf-8")


def test_n8n_dispatch_smoke_scripts_and_runbook_exist() -> None:
    assert (SCRIPT_DIR / "xhs_n8n_dispatch_search_smoke.ps1").exists()
    assert (SCRIPT_DIR / "xhs_n8n_dispatch_publish_smoke.ps1").exists()
    assert (SCRIPT_DIR / "xhs_n8n_dispatch_full_dry_run_smoke.ps1").exists()
    assert (SCRIPT_DIR / "xhs_n8n_dispatch_smoke_runbook.txt").exists()


def test_n8n_dispatch_smoke_scripts_default_to_local_dry_run() -> None:
    for name in [
        "xhs_n8n_dispatch_search_smoke.ps1",
        "xhs_n8n_dispatch_publish_smoke.ps1",
        "xhs_n8n_dispatch_full_dry_run_smoke.ps1",
    ]:
        content = _read(name)
        lowered = content.lower()
        assert "127.0.0.1" in content
        assert "dry_run" in lowered
        assert "/api/workflows/xhs/n8n-dispatch/" in content
        assert "127\\.0\\.0\\.1|localhost" in content
        assert "n8n.cloud" not in lowered
        assert "webhook.site" not in lowered
        assert "app_secret" not in lowered
        assert "access_token" not in lowered
        assert "xiaohongshu.com" not in lowered


def test_n8n_dispatch_smoke_runbook_mentions_safety_boundary() -> None:
    content = _read("xhs_n8n_dispatch_smoke_runbook.txt")

    assert "dry-run" in content.lower()
    assert "Do not call real n8n" in content
    assert "Do not call real n8n, real external webhook URLs" in content
    assert "Xiaohongshu" in content

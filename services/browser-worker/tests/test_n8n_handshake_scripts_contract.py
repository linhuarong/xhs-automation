from pathlib import Path


SCRIPT_DIR = Path("services/browser-worker/scripts")


def _read(name: str) -> str:
    return (SCRIPT_DIR / name).read_text(encoding="utf-8")


def test_n8n_handshake_scripts_and_runbook_exist() -> None:
    assert (SCRIPT_DIR / "xhs_n8n_handshake_ping_smoke.ps1").exists()
    assert (SCRIPT_DIR / "xhs_n8n_handshake_search_smoke.ps1").exists()
    assert (SCRIPT_DIR / "xhs_n8n_handshake_publish_smoke.ps1").exists()
    assert (SCRIPT_DIR / "xhs_n8n_handshake_full_smoke.ps1").exists()
    assert (SCRIPT_DIR / "xhs_n8n_handshake_smoke_runbook.txt").exists()


def test_n8n_handshake_scripts_default_to_local_dry_run_and_no_secret_prints() -> None:
    for name in [
        "xhs_n8n_handshake_ping_smoke.ps1",
        "xhs_n8n_handshake_search_smoke.ps1",
        "xhs_n8n_handshake_publish_smoke.ps1",
        "xhs_n8n_handshake_full_smoke.ps1",
    ]:
        content = _read(name)
        lowered = content.lower()
        assert "127.0.0.1" in content
        assert "dry_run" in lowered
        assert "-not $RealHandshake" in content
        assert "/api/workflows/xhs/n8n-handshake/" in content
        assert "127\\.0\\.0\\.1|localhost" in content
        assert "XHS_N8N_HANDSHAKE_SMOKE" in content
        assert "Write-Host \"$WebhookUrl" not in content
        assert "n8n.cloud" not in lowered
        assert "webhook.site" not in lowered
        assert "app_secret" not in lowered
        assert "access_token" not in lowered
        assert "xiaohongshu.com" not in lowered
        assert "while" not in lowered


def test_n8n_handshake_runbook_mentions_safety_boundary() -> None:
    content = _read("xhs_n8n_handshake_smoke_runbook.txt")

    assert "Dry-run by default" in content
    assert "Do not trigger Xiaohongshu search or publish" in content
    assert "Do not run retry loops" in content
    assert "Do not print full webhook URLs" in content
    assert "XHS_N8N_HANDSHAKE_ENABLED" in content

from pathlib import Path


SCRIPT_DIR = Path("services/browser-worker/scripts")


def _read(name: str) -> str:
    return (SCRIPT_DIR / name).read_text(encoding="utf-8")


def test_e2e_replay_scripts_exist() -> None:
    assert (SCRIPT_DIR / "xhs_e2e_replay_search.ps1").exists()
    assert (SCRIPT_DIR / "xhs_e2e_replay_publish.ps1").exists()
    assert (SCRIPT_DIR / "xhs_e2e_replay_all.ps1").exists()
    assert (SCRIPT_DIR / "xhs_e2e_replay_runbook.txt").exists()


def test_e2e_replay_scripts_only_allow_local_browser_worker_api() -> None:
    for name in ["xhs_e2e_replay_search.ps1", "xhs_e2e_replay_publish.ps1", "xhs_e2e_replay_all.ps1"]:
        content = _read(name)
        assert "127.0.0.1" in content
        assert "localhost" in content
        assert "feishu.cn" not in content.lower()
        assert "postgres://" not in content.lower()
        assert "postgresql://" not in content.lower()
        assert "minio" not in content.lower()
        assert "n8n.cloud" not in content.lower()
        assert "openclaw" not in content.lower()
        assert "xiaohongshu.com" not in content.lower()
        assert "YINGDAO_ACCESS_KEY" not in content


def test_e2e_replay_runbook_states_safety_boundary() -> None:
    content = _read("xhs_e2e_replay_runbook.txt")

    assert "Do not write real Feishu" in content
    assert "Do not connect real PostgreSQL" in content
    assert "Do not upload real MinIO" in content
    assert "Do not call real n8n" in content
    assert "Do not call real OpenClaw" in content
    assert "Do not open shop" in content
    assert "Do not open Xiaohongshu" in content
    assert "Do not click real publish" in content

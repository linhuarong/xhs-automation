from pathlib import Path


SCRIPTS = [
    "xhs_persistence_replay_feishu_search.ps1",
    "xhs_persistence_replay_feishu_publish.ps1",
    "xhs_persistence_replay_postgres_search.ps1",
    "xhs_persistence_replay_postgres_publish.ps1",
    "xhs_persistence_replay_minio_search.ps1",
    "xhs_persistence_replay_minio_publish.ps1",
    "xhs_persistence_replay_all.ps1",
]


def _script_root() -> Path:
    return Path(__file__).resolve().parents[1] / "scripts"


def test_persistence_replay_scripts_exist_and_call_local_api_only() -> None:
    root = _script_root()

    for script_name in SCRIPTS:
        path = root / script_name
        assert path.exists(), script_name
        text = path.read_text(encoding="utf-8")
        assert "/api/workflows/xhs/persistence-replay/" in text
        assert "Invoke-RestMethod" in text
        assert "FEISHU_" not in text
        assert "POSTGRES_DSN" not in text
        assert "MINIO_ENDPOINT" not in text
        assert "n8n.cloud" not in text.lower()
        assert "openclaw" not in text.lower() or "persistence-replay" in text


def test_persistence_replay_all_script_supports_search_and_publish() -> None:
    text = (_script_root() / "xhs_persistence_replay_all.ps1").read_text(encoding="utf-8")

    assert "ValidateSet(\"search\",\"publish\")" in text
    assert "/api/workflows/xhs/persistence-replay/all/$JobType" in text


def test_persistence_replay_runbook_contains_safety_boundaries() -> None:
    runbook = (_script_root() / "xhs_persistence_replay_runbook.txt").read_text(encoding="utf-8")

    assert "Do not write real Feishu" in runbook
    assert "Do not connect real PostgreSQL" in runbook
    assert "Do not upload real MinIO" in runbook
    assert "不要 open shop" in runbook
    assert "不要打开小红书" in runbook
    assert "不要点击真实发布" in runbook

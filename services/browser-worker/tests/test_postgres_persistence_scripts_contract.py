from pathlib import Path


SCRIPT_DIR = Path("services/browser-worker/scripts")
SCHEMA_PATH = Path("services/browser-worker/database/xhs_persistence_schema.sql")


def _read(name: str) -> str:
    return (SCRIPT_DIR / name).read_text(encoding="utf-8")


def test_postgres_persistence_scripts_and_runbook_exist() -> None:
    assert (SCRIPT_DIR / "xhs_postgres_schema_check.ps1").exists()
    assert (SCRIPT_DIR / "xhs_postgres_apply_schema.ps1").exists()
    assert (SCRIPT_DIR / "xhs_postgres_persist_search_replay.ps1").exists()
    assert (SCRIPT_DIR / "xhs_postgres_persist_publish_replay.ps1").exists()
    assert (SCRIPT_DIR / "xhs_postgres_persistence_runbook.txt").exists()
    assert SCHEMA_PATH.exists()


def test_postgres_persistence_scripts_default_to_dry_run_and_local_api() -> None:
    for name in [
        "xhs_postgres_schema_check.ps1",
        "xhs_postgres_persist_search_replay.ps1",
        "xhs_postgres_persist_publish_replay.ps1",
    ]:
        content = _read(name)
        assert "127.0.0.1" in content
        assert "dry_run" in content.lower() or "DryRun" in content
        assert "feishu.cn" not in content.lower()
        assert "minio" not in content.lower()
        assert "n8n.cloud" not in content.lower()
        assert "openclaw" not in content.lower()
        assert "xiaohongshu.com" not in content.lower()


def test_postgres_apply_schema_requires_confirm_apply() -> None:
    content = _read("xhs_postgres_apply_schema.ps1")

    assert "ConfirmApply" in content
    assert "No schema was applied" in content
    assert "psql" in content
    assert "password@" not in content.lower()


def test_postgres_schema_contains_required_tables_and_indexes() -> None:
    sql = SCHEMA_PATH.read_text(encoding="utf-8")

    for table in [
        "xhs_search_evidence",
        "xhs_search_records",
        "xhs_publish_evidence",
        "xhs_publish_jobs",
        "xhs_task_log",
        "xhs_workflow_log",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
    assert "CREATE INDEX IF NOT EXISTS" in sql

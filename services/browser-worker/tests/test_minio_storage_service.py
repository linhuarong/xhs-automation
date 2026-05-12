import json
from pathlib import Path

from app.schemas import XhsMinioStorageRequest, XhsMinioUploadSource
from app.services.minio_storage_service import MinioStorageService
from app.utils.errors import MINIO_SENSITIVE_FILE_BLOCKED, MINIO_SOURCE_NOT_FOUND, MINIO_UPLOAD_DISABLED


def _write(path, content="ok"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _service(tmp_path, env=None, client_factory=None):
    return MinioStorageService(worker_root=tmp_path, env=env or {}, minio_client_factory=client_factory)


def test_minio_default_dry_run_does_not_upload(tmp_path) -> None:
    source = _write(tmp_path / ".local_evidence" / "search-1" / "search_evidence.json", "{}")
    service = _service(tmp_path, client_factory=lambda: (_ for _ in ()).throw(AssertionError("should not connect")))

    result = service.upload_search_artifacts(
        XhsMinioStorageRequest(
            job_id="search-1",
            job_type="search",
            account_id="xhs_dev_01",
            sources=[XhsMinioUploadSource(source_path=str(source), artifact_type="evidence_json")],
            dry_run=True,
        )
    )

    assert result.status == "success"
    assert result.uploaded_count == 0
    assert result.real_upload_allowed is False
    assert Path(result.plan_path).exists()
    assert json.loads(Path(result.summary_path).read_text(encoding="utf-8"))["uploaded_count"] == 0


def test_minio_env_not_enabled_blocks_real_upload(tmp_path) -> None:
    source = _write(tmp_path / ".local_evidence" / "search-1" / "search_evidence.json", "{}")
    result = _service(tmp_path).upload_search_artifacts(
        XhsMinioStorageRequest(
            job_id="search-1",
            job_type="search",
            account_id="xhs_dev_01",
            sources=[XhsMinioUploadSource(source_path=str(source), artifact_type="evidence_json")],
            dry_run=False,
        )
    )

    assert result.status == "failed"
    assert result.error_code == MINIO_UPLOAD_DISABLED
    assert result.uploaded_count == 0


def test_minio_double_switch_required_for_upload(tmp_path) -> None:
    source = _write(tmp_path / ".local_evidence" / "search-1" / "search_evidence.json", "{}")
    env = {
        "XHS_MINIO_UPLOAD_ENABLED": "true",
        "XHS_ALLOW_REAL_MINIO_UPLOAD": "false",
        "XHS_MINIO_ENDPOINT": "http://127.0.0.1:9000",
        "XHS_MINIO_ACCESS_KEY": "local-test",
        "XHS_MINIO_SECRET_KEY": "local-test",
        "XHS_MINIO_BUCKET": "xhs-assets",
    }
    result = _service(tmp_path, env=env).upload_search_artifacts(
        XhsMinioStorageRequest(
            job_id="search-1",
            job_type="search",
            account_id="xhs_dev_01",
            sources=[XhsMinioUploadSource(source_path=str(source), artifact_type="evidence_json")],
            dry_run=False,
        )
    )

    assert result.status == "failed"
    assert result.error_code == MINIO_UPLOAD_DISABLED


def test_minio_sources_generate_plan_and_safe_object_key(tmp_path) -> None:
    source = _write(tmp_path / ".local_evidence" / "search-1" / "xhs_search_smoke.png", "png")
    service = _service(tmp_path)

    key = service.build_object_key("search", "xhs_dev_01", "../search-1", source, "screenshot")
    plan = service.build_upload_plan(
        XhsMinioStorageRequest(
            job_id="search-1",
            job_type="search",
            account_id="xhs_dev_01",
            sources=[XhsMinioUploadSource(source_path=str(source), artifact_type="screenshot")],
        )
    )

    assert "G:" not in key
    assert ".." not in key
    assert "\\" not in key
    assert key.startswith("xhs/search/xhs_dev_01/")
    assert plan.items[0].exists is True
    assert plan.items[0].sha256.startswith("sha256:")


def test_minio_optional_missing_does_not_fail_required_missing_fails(tmp_path) -> None:
    service = _service(tmp_path)
    optional = service.upload_search_artifacts(
        XhsMinioStorageRequest(
            job_id="search-optional",
            job_type="search",
            account_id="xhs_dev_01",
            sources=[XhsMinioUploadSource(source_path=".local_evidence/missing/optional.png", artifact_type="screenshot", required=False)],
        )
    )
    required = service.upload_search_artifacts(
        XhsMinioStorageRequest(
            job_id="search-required",
            job_type="search",
            account_id="xhs_dev_01",
            sources=[XhsMinioUploadSource(source_path=".local_evidence/missing/search_evidence.json", artifact_type="evidence_json", required=True)],
        )
    )

    assert optional.status == "success"
    assert required.status == "failed"
    assert required.error_code == MINIO_SOURCE_NOT_FOUND


def test_minio_sensitive_paths_are_blocked(tmp_path) -> None:
    source = _write(tmp_path / ".env", "SECRET=change_me")
    result = _service(tmp_path).upload_search_artifacts(
        XhsMinioStorageRequest(
            job_id="search-sensitive",
            job_type="search",
            account_id="xhs_dev_01",
            sources=[XhsMinioUploadSource(source_path=str(source), artifact_type="evidence_json")],
        )
    )

    assert result.status == "failed"
    assert result.error_code == MINIO_SENSITIVE_FILE_BLOCKED
    assert result.sensitive_file_detected is True


def test_minio_evidence_dir_auto_discovers_standard_files(tmp_path) -> None:
    evidence_dir = tmp_path / ".local_evidence" / "search-auto"
    _write(evidence_dir / "search_evidence.json", "{}")
    _write(evidence_dir / "xhs_search_smoke.png", "png")

    result = _service(tmp_path).upload_search_artifacts(
        XhsMinioStorageRequest(
            job_id="search-auto",
            job_type="search",
            account_id="xhs_dev_01",
            evidence_dir=str(evidence_dir),
        )
    )
    summary = json.loads(Path(result.summary_path).read_text(encoding="utf-8"))

    assert result.status == "success"
    assert summary["total_sources"] == 5
    assert summary["existing_sources"] == 2
    assert summary["uploaded_count"] == 0


def test_minio_publish_evidence_dir_auto_discovers_standard_files(tmp_path) -> None:
    evidence_dir = tmp_path / ".local_evidence" / "publish-auto"
    _write(evidence_dir / "publish_evidence.json", "{}")
    _write(evidence_dir / "publish_result.png", "png")

    result = _service(tmp_path).upload_publish_artifacts(
        XhsMinioStorageRequest(
            job_id="publish-auto",
            job_type="publish",
            account_id="xhs_dev_01",
            evidence_dir=str(evidence_dir),
        )
    )
    summary = json.loads(Path(result.summary_path).read_text(encoding="utf-8"))

    assert result.status == "success"
    assert summary["total_sources"] == 5
    assert summary["existing_sources"] == 2
    assert summary["real_upload_allowed"] is False

import json

import pytest

from app.services.xhs_storage_service import MinioStorageAdapter, XhsStorageService
from app.utils.errors import MINIO_ADAPTER_NOT_CONFIGURED, WorkerError


def test_archive_evidence_with_missing_screenshot(tmp_path) -> None:
    evidence_root = tmp_path / ".local_evidence"
    archive_root = tmp_path / ".local_archive"
    job_dir = evidence_root / "job-1"
    job_dir.mkdir(parents=True)
    (job_dir / "search_evidence.json").write_text('{"status":"success"}', encoding="utf-8")

    manifest = XhsStorageService(evidence_root, archive_root).archive_evidence("job-1")
    manifest_path = archive_root / "xhs" / "job-1" / "manifest.json"
    raw = manifest_path.read_bytes()

    assert raw[:3] != b"\xef\xbb\xbf"
    assert manifest["job_id"] == "job-1"
    assert (archive_root / "xhs" / "job-1" / "search_evidence.json").exists()
    assert [entry["status"] for entry in manifest["files"]] == ["archived", "missing", "missing"]
    assert json.loads(raw.decode("utf-8"))["job_id"] == "job-1"


def test_archive_evidence_with_screenshots(tmp_path) -> None:
    evidence_root = tmp_path / ".local_evidence"
    archive_root = tmp_path / ".local_archive"
    job_dir = evidence_root / "job-1"
    job_dir.mkdir(parents=True)
    for filename in ("search_evidence.json", "xhs_search_smoke.png", "xhs_search_before_scroll.png"):
        (job_dir / filename).write_text(filename, encoding="utf-8")

    manifest = XhsStorageService(evidence_root, archive_root).archive_evidence("job-1")

    assert [entry["status"] for entry in manifest["files"]] == ["archived", "archived", "archived"]


def test_minio_adapter_skeleton_raises() -> None:
    with pytest.raises(WorkerError) as exc:
        MinioStorageAdapter().archive_file(__file__, __file__)

    assert exc.value.error_code == MINIO_ADAPTER_NOT_CONFIGURED

import json

from app.services.xhs_storage_service import XhsStorageService


def test_archive_publish_evidence_missing_screenshots_do_not_fail(tmp_path) -> None:
    evidence_root = tmp_path / ".local_evidence"
    archive_root = tmp_path / ".local_archive"
    job_dir = evidence_root / "publish-1"
    job_dir.mkdir(parents=True)
    (job_dir / "publish_evidence.json").write_text('{"status":"success"}', encoding="utf-8")

    manifest = XhsStorageService(evidence_root, archive_root).archive_publish_evidence("publish-1")
    manifest_path = archive_root / "xhs_publish" / "publish-1" / "manifest.json"
    raw = manifest_path.read_bytes()

    assert raw[:3] != b"\xef\xbb\xbf"
    assert manifest["job_id"] == "publish-1"
    assert [entry["status"] for entry in manifest["files"]] == ["archived", "missing", "missing", "missing"]
    assert json.loads(raw.decode("utf-8"))["job_id"] == "publish-1"


def test_archive_publish_evidence_with_screenshots(tmp_path) -> None:
    evidence_root = tmp_path / ".local_evidence"
    archive_root = tmp_path / ".local_archive"
    job_dir = evidence_root / "publish-1"
    job_dir.mkdir(parents=True)
    for filename in (
        "publish_evidence.json",
        "publish_before.png",
        "publish_form_filled.png",
        "publish_result.png",
    ):
        (job_dir / filename).write_text(filename, encoding="utf-8")

    manifest = XhsStorageService(evidence_root, archive_root).archive_publish_evidence("publish-1")

    assert [entry["status"] for entry in manifest["files"]] == ["archived", "archived", "archived", "archived"]

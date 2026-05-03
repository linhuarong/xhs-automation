from pathlib import Path

import pytest

from app.services import image_downloader
from app.services.image_downloader import download_images
from app.utils import IMAGE_DOWNLOAD_FAILED, WorkerError


class FakeResponse:
    def __init__(self, content: bytes, content_type: str = "image/png") -> None:
        self._content = content
        self.headers = {"Content-Type": content_type}

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args) -> None:
        return None

    def read(self) -> bytes:
        return self._content


def test_download_images_saves_files(monkeypatch, tmp_path) -> None:
    def fake_urlopen(image_url: str) -> FakeResponse:
        return FakeResponse(f"content:{image_url}".encode())

    monkeypatch.setattr(image_downloader, "urlopen", fake_urlopen)

    results = download_images(
        job_id="job-1",
        image_urls=[
            "https://example.com/path/a.png",
            "https://example.com/no-extension",
        ],
        download_root=str(tmp_path),
    )

    assert [result.filename for result in results] == [
        "001_a.png",
        "002_no-extension",
    ]
    assert results[0].content_type == "image/png"
    assert Path(results[0].local_path).read_bytes() == (
        b"content:https://example.com/path/a.png"
    )
    assert Path(results[1].local_path).exists()


def test_download_images_uses_image_when_url_has_no_filename(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        image_downloader,
        "urlopen",
        lambda image_url: FakeResponse(b"image-content"),
    )

    results = download_images(
        job_id="job-2",
        image_urls=["https://example.com/"],
        download_root=str(tmp_path),
    )

    assert results[0].filename == "001_image"
    assert Path(results[0].local_path).read_bytes() == b"image-content"


def test_download_images_rejects_empty_urls() -> None:
    with pytest.raises(WorkerError) as exc_info:
        download_images(job_id="job-3", image_urls=[])

    assert exc_info.value.error_code == IMAGE_DOWNLOAD_FAILED
    assert exc_info.value.retryable is True


def test_download_images_rejects_non_http_urls() -> None:
    with pytest.raises(WorkerError) as exc_info:
        download_images(job_id="job-4", image_urls=["file:///tmp/a.png"])

    assert exc_info.value.error_code == IMAGE_DOWNLOAD_FAILED
    assert exc_info.value.retryable is True


def test_download_images_wraps_download_failure(monkeypatch, tmp_path) -> None:
    def fake_urlopen(image_url: str) -> FakeResponse:
        raise OSError("network unavailable")

    monkeypatch.setattr(image_downloader, "urlopen", fake_urlopen)

    with pytest.raises(WorkerError) as exc_info:
        download_images(
            job_id="job-5",
            image_urls=["https://example.com/a.png"],
            download_root=str(tmp_path),
        )

    assert exc_info.value.error_code == IMAGE_DOWNLOAD_FAILED
    assert exc_info.value.retryable is True

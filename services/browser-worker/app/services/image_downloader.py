from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import urlopen

from app.utils import IMAGE_DOWNLOAD_FAILED, WorkerError


@dataclass
class ImageDownloadResult:
    """Local result for a downloaded image."""

    source_url: str
    local_path: str
    filename: str
    content_type: str | None = None


def _build_filename(index: int, image_url: str) -> str:
    """Build a local filename for an image URL."""
    parsed = urlparse(image_url)
    source_name = Path(unquote(parsed.path)).name or "image"
    return f"{index:03d}_{source_name}"


def _validate_image_urls(image_urls: list[str]) -> None:
    """Validate image URL input."""
    if not image_urls:
        raise WorkerError(
            error_code=IMAGE_DOWNLOAD_FAILED,
            error_message="image_urls cannot be empty",
            retryable=True,
        )

    for image_url in image_urls:
        parsed = urlparse(image_url)
        if parsed.scheme not in {"http", "https"}:
            raise WorkerError(
                error_code=IMAGE_DOWNLOAD_FAILED,
                error_message=f"unsupported image URL scheme: {image_url}",
                retryable=True,
            )


def download_images(
    job_id: str,
    image_urls: list[str],
    download_root: str = ".local_downloads",
) -> list[ImageDownloadResult]:
    """Download images into a local job directory."""
    _validate_image_urls(image_urls)

    job_dir = Path(download_root) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    results: list[ImageDownloadResult] = []
    for index, image_url in enumerate(image_urls, start=1):
        filename = _build_filename(index, image_url)
        local_path = job_dir / filename

        try:
            with urlopen(image_url) as response:
                content = response.read()
                content_type = response.headers.get("Content-Type")
        except Exception as exc:
            raise WorkerError(
                error_code=IMAGE_DOWNLOAD_FAILED,
                error_message=f"failed to download image: {image_url}",
                retryable=True,
            ) from exc

        try:
            local_path.write_bytes(content)
        except Exception as exc:
            raise WorkerError(
                error_code=IMAGE_DOWNLOAD_FAILED,
                error_message=f"failed to save image: {local_path}",
                retryable=True,
            ) from exc

        results.append(
            ImageDownloadResult(
                source_url=image_url,
                local_path=str(local_path),
                filename=filename,
                content_type=content_type,
            )
        )

    return results

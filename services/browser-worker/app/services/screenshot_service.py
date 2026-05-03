from pathlib import Path
from typing import Any

from app.utils import SCREENSHOT_FAILED, WorkerError


def save_screenshot(
    driver: Any,
    job_id: str,
    name: str,
    screenshot_root: str = ".local_screenshots",
) -> str:
    """Save a local screenshot for a job."""
    screenshot_dir = Path(screenshot_root) / job_id
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshot_dir / f"{name}.png"

    try:
        saved = driver.save_screenshot(str(screenshot_path))
    except Exception as exc:
        raise WorkerError(
            error_code=SCREENSHOT_FAILED,
            error_message=f"failed to save screenshot: {screenshot_path}",
            retryable=True,
        ) from exc

    if saved is False:
        raise WorkerError(
            error_code=SCREENSHOT_FAILED,
            error_message=f"failed to save screenshot: {screenshot_path}",
            retryable=True,
        )

    return str(screenshot_path)

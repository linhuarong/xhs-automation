from pathlib import Path

import pytest

from app.services.screenshot_service import save_screenshot
from app.utils import SCREENSHOT_FAILED, WorkerError


class FakeDriver:
    def __init__(self, saved: bool = True, raises: bool = False) -> None:
        self.saved = saved
        self.raises = raises
        self.paths: list[str] = []

    def save_screenshot(self, path: str) -> bool:
        self.paths.append(path)
        if self.raises:
            raise RuntimeError("screenshot failed")
        Path(path).write_bytes(b"png")
        return self.saved


def test_save_screenshot_returns_local_path(tmp_path) -> None:
    driver = FakeDriver()

    path = save_screenshot(driver, "job-1", "before", str(tmp_path))

    assert path == str(tmp_path / "job-1" / "before.png")
    assert Path(path).read_bytes() == b"png"


def test_save_screenshot_raises_when_driver_returns_false(tmp_path) -> None:
    driver = FakeDriver(saved=False)

    with pytest.raises(WorkerError) as exc_info:
        save_screenshot(driver, "job-1", "before", str(tmp_path))

    assert exc_info.value.error_code == SCREENSHOT_FAILED
    assert exc_info.value.retryable is True


def test_save_screenshot_raises_when_driver_raises(tmp_path) -> None:
    driver = FakeDriver(raises=True)

    with pytest.raises(WorkerError) as exc_info:
        save_screenshot(driver, "job-1", "before", str(tmp_path))

    assert exc_info.value.error_code == SCREENSHOT_FAILED
    assert exc_info.value.retryable is True

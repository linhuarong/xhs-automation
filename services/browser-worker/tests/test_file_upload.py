import pytest

from app.utils import IMAGE_UPLOAD_FAILED, WorkerError
from app.utils.file_upload import upload_files_to_input


class FakeFileInput:
    def __init__(self, raises: bool = False) -> None:
        self.raises = raises
        self.value: str | None = None

    def send_keys(self, value: str) -> None:
        if self.raises:
            raise RuntimeError("send_keys failed")
        self.value = value


def test_upload_files_to_input_sends_newline_joined_paths(tmp_path) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    file_input = FakeFileInput()

    upload_files_to_input(file_input, [str(first), str(second)])

    assert file_input.value == f"{first}\n{second}"


def test_upload_files_to_input_rejects_empty_paths() -> None:
    with pytest.raises(WorkerError) as exc_info:
        upload_files_to_input(FakeFileInput(), [])

    assert exc_info.value.error_code == IMAGE_UPLOAD_FAILED
    assert exc_info.value.retryable is True


def test_upload_files_to_input_rejects_missing_path(tmp_path) -> None:
    missing = tmp_path / "missing.png"

    with pytest.raises(WorkerError) as exc_info:
        upload_files_to_input(FakeFileInput(), [str(missing)])

    assert exc_info.value.error_code == IMAGE_UPLOAD_FAILED
    assert exc_info.value.retryable is True


def test_upload_files_to_input_wraps_send_keys_failure(tmp_path) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(b"image")

    with pytest.raises(WorkerError) as exc_info:
        upload_files_to_input(FakeFileInput(raises=True), [str(image)])

    assert exc_info.value.error_code == IMAGE_UPLOAD_FAILED
    assert exc_info.value.retryable is True

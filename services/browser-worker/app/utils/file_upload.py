from pathlib import Path
from typing import Any

from app.utils.errors import IMAGE_UPLOAD_FAILED, WorkerError


def upload_files_to_input(file_input: Any, file_paths: list[str]) -> None:
    """Send local file paths to a file input element."""
    if not file_paths:
        raise WorkerError(
            error_code=IMAGE_UPLOAD_FAILED,
            error_message="file_paths cannot be empty",
            retryable=True,
        )

    missing_paths = [file_path for file_path in file_paths if not Path(file_path).exists()]
    if missing_paths:
        raise WorkerError(
            error_code=IMAGE_UPLOAD_FAILED,
            error_message=f"file path does not exist: {missing_paths[0]}",
            retryable=True,
        )

    try:
        file_input.send_keys("\n".join(file_paths))
    except Exception as exc:
        raise WorkerError(
            error_code=IMAGE_UPLOAD_FAILED,
            error_message="failed to upload files to input",
            retryable=True,
        ) from exc

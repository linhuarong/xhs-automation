LOGIN_REQUIRED = "LOGIN_REQUIRED"
WAITING_HUMAN_VERIFICATION = "WAITING_HUMAN_VERIFICATION"
PROFILE_START_FAILED = "PROFILE_START_FAILED"
DRIVER_CONNECT_FAILED = "DRIVER_CONNECT_FAILED"
IMAGE_DOWNLOAD_FAILED = "IMAGE_DOWNLOAD_FAILED"
IMAGE_UPLOAD_FAILED = "IMAGE_UPLOAD_FAILED"
SCREENSHOT_FAILED = "SCREENSHOT_FAILED"
ELEMENT_NOT_FOUND = "ELEMENT_NOT_FOUND"
CONTENT_REJECTED = "CONTENT_REJECTED"
SUBMIT_FAILED = "SUBMIT_FAILED"
NOTE_URL_NOT_FOUND = "NOTE_URL_NOT_FOUND"
ACCOUNT_RESTRICTED = "ACCOUNT_RESTRICTED"
UNKNOWN_ERROR = "UNKNOWN_ERROR"


class WorkerError(Exception):
    """Structured browser-worker error."""

    def __init__(
        self,
        error_code: str,
        error_message: str,
        retryable: bool = False,
    ) -> None:
        """Create a worker error."""
        self.error_code = error_code
        self.error_message = error_message
        self.retryable = retryable
        super().__init__(error_message)

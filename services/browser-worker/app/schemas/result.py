from pydantic import BaseModel


STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_WAITING_HUMAN_VERIFICATION = "waiting_human_verification"
STATUS_ACCEPTED = "accepted"


class WorkerResult(BaseModel):
    """Result returned by browser-worker after handling a job."""

    job_id: str
    status: str
    message: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    screenshot_url: str | None = None
    note_url: str | None = None
    items: list[dict] | None = None

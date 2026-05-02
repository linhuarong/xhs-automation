from dataclasses import dataclass
from datetime import datetime, timezone


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobStatus:
    """In-memory status for a browser-worker job."""

    job_id: str
    task_type: str
    status: str
    current_step: str | None = None
    message: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    updated_at: str = ""


class JobRegistry:
    """In-memory browser-worker job registry."""

    def __init__(self) -> None:
        """Create an empty job registry."""
        self._jobs: dict[str, JobStatus] = {}

    def create_job(
        self,
        job_id: str,
        task_type: str,
        status: str = "accepted",
    ) -> JobStatus:
        """Create and store a job status."""
        job_status = JobStatus(
            job_id=job_id,
            task_type=task_type,
            status=status,
            updated_at=_utc_now_iso(),
        )
        self._jobs[job_id] = job_status
        return job_status

    def update_job(self, job_id: str, **kwargs) -> JobStatus:
        """Update and return a stored job status."""
        job_status = self._jobs[job_id]
        for key, value in kwargs.items():
            if not hasattr(job_status, key):
                raise ValueError(f"Unknown JobStatus field: {key}")
            if key == "job_id":
                raise ValueError("job_id cannot be updated.")
            setattr(job_status, key, value)

        job_status.updated_at = _utc_now_iso()
        return job_status

    def get_job(self, job_id: str) -> JobStatus | None:
        """Return a job status by id."""
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[JobStatus]:
        """Return all stored job statuses."""
        return list(self._jobs.values())


job_registry = JobRegistry()

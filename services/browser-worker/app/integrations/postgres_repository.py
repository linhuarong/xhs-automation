from abc import ABC, abstractmethod

from app.utils.errors import POSTGRES_REPOSITORY_NOT_CONFIGURED, WorkerError


class XhsRepository(ABC):
    """Boundary for XHS PostgreSQL persistence."""

    @abstractmethod
    def save_job_result(self, result: dict) -> dict:
        """Save one job result."""

    @abstractmethod
    def save_normalized_records(self, records: list[dict]) -> list[dict]:
        """Save normalized records."""

    @abstractmethod
    def get_job(self, job_id: str) -> dict | None:
        """Get one job by id."""

    @abstractmethod
    def list_jobs(self, batch_id: str) -> list[dict]:
        """List jobs for a batch id."""

    @abstractmethod
    def save_publish_result(self, result: dict) -> dict:
        """Save one publish result."""

    @abstractmethod
    def get_publish_job(self, job_id: str) -> dict | None:
        """Get one publish job by id."""

    @abstractmethod
    def list_publish_jobs(self, batch_id: str) -> list[dict]:
        """List publish jobs for a batch id."""

    @abstractmethod
    def save_workflow_result(self, result: dict) -> dict:
        """Save one workflow result."""

    @abstractmethod
    def get_workflow_result(self, workflow_id: str) -> dict | None:
        """Get one workflow result."""


class NotConfiguredXhsRepository(XhsRepository):
    """Placeholder repository that never connects to PostgreSQL."""

    def save_job_result(self, result: dict) -> dict:
        raise self._error()

    def save_normalized_records(self, records: list[dict]) -> list[dict]:
        raise self._error()

    def get_job(self, job_id: str) -> dict | None:
        raise self._error()

    def list_jobs(self, batch_id: str) -> list[dict]:
        raise self._error()

    def save_publish_result(self, result: dict) -> dict:
        raise self._error()

    def get_publish_job(self, job_id: str) -> dict | None:
        raise self._error()

    def list_publish_jobs(self, batch_id: str) -> list[dict]:
        raise self._error()

    def save_workflow_result(self, result: dict) -> dict:
        raise self._error()

    def get_workflow_result(self, workflow_id: str) -> dict | None:
        raise self._error()

    def _error(self) -> WorkerError:
        return WorkerError(
            error_code=POSTGRES_REPOSITORY_NOT_CONFIGURED,
            error_message="XHS PostgreSQL repository is not configured.",
            retryable=False,
        )


class InMemoryXhsRepository(XhsRepository):
    """In-memory repository for tests and local dry-runs."""

    def __init__(self) -> None:
        """Create empty in-memory stores."""
        self.jobs: dict[str, dict] = {}
        self.normalized_records: list[dict] = []
        self.publish_jobs: dict[str, dict] = {}
        self.workflow_results: dict[str, dict] = {}

    def save_job_result(self, result: dict) -> dict:
        job_id = str(result.get("job_id", ""))
        self.jobs[job_id] = result
        return result

    def save_normalized_records(self, records: list[dict]) -> list[dict]:
        self.normalized_records.extend(records)
        return records

    def get_job(self, job_id: str) -> dict | None:
        return self.jobs.get(job_id)

    def list_jobs(self, batch_id: str) -> list[dict]:
        prefix = f"{batch_id}-"
        return [
            job
            for job_id, job in self.jobs.items()
            if job.get("batch_id") == batch_id or job_id.startswith(prefix)
        ]

    def save_publish_result(self, result: dict) -> dict:
        job_id = str(result.get("job_id", ""))
        self.publish_jobs[job_id] = result
        return result

    def get_publish_job(self, job_id: str) -> dict | None:
        return self.publish_jobs.get(job_id)

    def list_publish_jobs(self, batch_id: str) -> list[dict]:
        prefix = f"{batch_id}-"
        return [
            job
            for job_id, job in self.publish_jobs.items()
            if job.get("batch_id") == batch_id or job_id.startswith(prefix)
        ]

    def save_workflow_result(self, result: dict) -> dict:
        workflow_id = str(result.get("workflow_id", ""))
        self.workflow_results[workflow_id] = result
        return result

    def get_workflow_result(self, workflow_id: str) -> dict | None:
        return self.workflow_results.get(workflow_id)

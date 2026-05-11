from copy import deepcopy
from datetime import UTC, datetime
from typing import Any


SUPPORTED_JOB_STATUSES = {
    "pending",
    "processing",
    "success",
    "failed",
    "waiting_human_verification",
    "not_found",
}


class InMemoryXhsJobRegistry:
    """In-memory registry for XHS search, publish, and batch jobs."""

    def __init__(self) -> None:
        """Create empty registry stores."""
        self.jobs: dict[str, dict] = {}
        self.batches: dict[str, dict] = {}

    def register_job(self, job_id: str, job_type: str, payload: dict | None = None) -> dict:
        """Register a job as pending."""
        now = self._utc_now_iso()
        job = {
            "job_id": job_id,
            "job_type": job_type,
            "status": "pending",
            "payload": deepcopy(payload or {}),
            "result": None,
            "error_code": None,
            "error_message": None,
            "created_at": now,
            "updated_at": now,
        }
        self.jobs[job_id] = job
        return deepcopy(job)

    def update_job_status(
        self,
        job_id: str,
        status: str,
        result: dict | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> dict:
        """Update a registered job status."""
        job = self.jobs.get(job_id)
        if job is None:
            job = self.register_job(job_id, "unknown", {})
        if status not in SUPPORTED_JOB_STATUSES:
            status = "failed"
        self.jobs[job_id] = {
            **job,
            "status": status,
            "result": deepcopy(result),
            "error_code": error_code,
            "error_message": error_message,
            "updated_at": self._utc_now_iso(),
        }
        return deepcopy(self.jobs[job_id])

    def get_job(self, job_id: str) -> dict:
        """Return a job or a not_found marker."""
        job = self.jobs.get(job_id)
        if job is None:
            return {
                "job_id": job_id,
                "job_type": None,
                "status": "not_found",
                "payload": {},
                "result": None,
                "error_code": "XHS_JOB_NOT_FOUND",
                "error_message": f"XHS job not found: {job_id}",
            }
        return deepcopy(job)

    def list_jobs(self, batch_id: str | None = None) -> list[dict]:
        """List all jobs, optionally by batch id."""
        jobs = list(self.jobs.values())
        if batch_id is not None:
            jobs = [
                job
                for job in jobs
                if job.get("payload", {}).get("batch_id") == batch_id
                or str(job.get("job_id", "")).startswith(f"{batch_id}-")
            ]
        return deepcopy(jobs)

    def register_batch(self, batch_id: str, batch_type: str, job_ids: list[str]) -> dict:
        """Register a batch as pending."""
        now = self._utc_now_iso()
        batch = {
            "batch_id": batch_id,
            "batch_type": batch_type,
            "job_ids": list(job_ids),
            "status": "pending",
            "summary": {},
            "created_at": now,
            "updated_at": now,
        }
        self.batches[batch_id] = batch
        return deepcopy(batch)

    def update_batch_summary(self, batch_id: str, summary: dict) -> dict:
        """Update a batch summary."""
        batch = self.batches.get(batch_id)
        if batch is None:
            batch = self.register_batch(batch_id, "unknown", [])
        status = summary.get("status") or batch.get("status")
        self.batches[batch_id] = {
            **batch,
            "status": status,
            "summary": deepcopy(summary),
            "updated_at": self._utc_now_iso(),
        }
        return deepcopy(self.batches[batch_id])

    def get_batch(self, batch_id: str) -> dict:
        """Return a batch or a not_found marker."""
        batch = self.batches.get(batch_id)
        if batch is None:
            return {
                "batch_id": batch_id,
                "batch_type": None,
                "job_ids": [],
                "status": "not_found",
                "summary": {},
                "error_code": "XHS_JOB_NOT_FOUND",
                "error_message": f"XHS batch not found: {batch_id}",
            }
        return deepcopy(batch)

    def _utc_now_iso(self) -> str:
        """Return a UTC timestamp."""
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")


xhs_job_registry = InMemoryXhsJobRegistry()

from abc import ABC, abstractmethod

from app.utils.errors import FEISHU_ADAPTER_NOT_CONFIGURED, WorkerError


class FeishuAdapter(ABC):
    """Boundary for Feishu writes."""

    @abstractmethod
    def upsert_keyword_result(self, record: dict) -> dict:
        """Upsert one normalized keyword result."""

    @abstractmethod
    def upsert_batch_summary(self, summary: dict) -> dict:
        """Upsert one batch summary."""

    @abstractmethod
    def attach_evidence(self, job_id: str, files: list[dict]) -> dict:
        """Attach evidence metadata to a Feishu record."""

    @abstractmethod
    def upsert_publish_result(self, result: dict) -> dict:
        """Upsert one publish result."""

    @abstractmethod
    def upsert_publish_batch_summary(self, summary: dict) -> dict:
        """Upsert one publish batch summary."""

    @abstractmethod
    def attach_publish_evidence(self, job_id: str, files: list[dict]) -> dict:
        """Attach publish evidence metadata to a Feishu record."""


class NotConfiguredFeishuAdapter(FeishuAdapter):
    """Placeholder adapter that never calls real Feishu."""

    def upsert_keyword_result(self, record: dict) -> dict:
        raise self._error()

    def upsert_batch_summary(self, summary: dict) -> dict:
        raise self._error()

    def attach_evidence(self, job_id: str, files: list[dict]) -> dict:
        raise self._error()

    def upsert_publish_result(self, result: dict) -> dict:
        raise self._error()

    def upsert_publish_batch_summary(self, summary: dict) -> dict:
        raise self._error()

    def attach_publish_evidence(self, job_id: str, files: list[dict]) -> dict:
        raise self._error()

    def _error(self) -> WorkerError:
        return WorkerError(
            error_code=FEISHU_ADAPTER_NOT_CONFIGURED,
            error_message="Feishu adapter is not configured.",
            retryable=False,
        )


class MockFeishuAdapter(FeishuAdapter):
    """In-memory Feishu adapter for tests and dry-runs."""

    def __init__(self) -> None:
        """Create an empty mock adapter."""
        self.keyword_results: list[dict] = []
        self.batch_summaries: list[dict] = []
        self.evidence_attachments: list[dict] = []
        self.publish_results: list[dict] = []
        self.publish_batch_summaries: list[dict] = []
        self.publish_evidence_attachments: list[dict] = []

    def upsert_keyword_result(self, record: dict) -> dict:
        self.keyword_results.append(record)
        return {"status": "success", "record": record}

    def upsert_batch_summary(self, summary: dict) -> dict:
        self.batch_summaries.append(summary)
        return {"status": "success", "summary": summary}

    def attach_evidence(self, job_id: str, files: list[dict]) -> dict:
        attachment = {"job_id": job_id, "files": files}
        self.evidence_attachments.append(attachment)
        return {"status": "success", **attachment}

    def upsert_publish_result(self, result: dict) -> dict:
        self.publish_results.append(result)
        return {"status": "success", "result": result}

    def upsert_publish_batch_summary(self, summary: dict) -> dict:
        self.publish_batch_summaries.append(summary)
        return {"status": "success", "summary": summary}

    def attach_publish_evidence(self, job_id: str, files: list[dict]) -> dict:
        attachment = {"job_id": job_id, "files": files}
        self.publish_evidence_attachments.append(attachment)
        return {"status": "success", **attachment}

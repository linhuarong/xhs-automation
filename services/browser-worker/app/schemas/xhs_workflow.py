from typing import Literal

from pydantic import BaseModel, Field


class XhsSearchToPublishWorkflowRequest(BaseModel):
    """Mock search-to-publish workflow request."""

    workflow_id: str
    account_id: str
    search_provider_type: str = "mock"
    publish_provider_type: str = "mock"
    keywords: list[str]
    limit: int = 20
    max_publish_jobs: int = 1
    mode: Literal["mock"] = "mock"


class XhsWorkflowResult(BaseModel):
    """Workflow result summary."""

    workflow_id: str
    status: str
    search_batch_id: str | None = None
    publish_batch_id: str | None = None
    search_summary: dict = Field(default_factory=dict)
    publish_summary: dict = Field(default_factory=dict)
    archived_files: list[dict] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    created_at: str
    finished_at: str | None = None

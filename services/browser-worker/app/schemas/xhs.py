from typing import Literal

from pydantic import BaseModel, Field


class XhsSearchItem(BaseModel):
    """One visible XHS keyword search result from RPA evidence."""

    rank: int | None = None
    title: str | None = None
    note_url: str | None = None
    author_name: str | None = None
    author_url: str | None = None
    like_count: int | str | None = None
    collect_count: int | str | None = None
    comment_count: int | str | None = None
    cover_url: str | None = None
    raw_text: str | None = None
    tags: list[str] = Field(default_factory=list)
    captured_at: str | None = None


class XhsNormalizedRecord(BaseModel):
    """Normalized record consumed by storage, Feishu, and later analysis."""

    job_id: str | None = None
    keyword: str | None = None
    account_id: str | None = None
    provider_type: str | None = None
    rank: int | None = None
    title: str | None = None
    note_url: str | None = None
    author_name: str | None = None
    like_count: int | str | None = None
    collect_count: int | str | None = None
    comment_count: int | str | None = None
    engagement_score: float | int | None = None
    evidence_json_path: str | None = None
    screenshot_path: str | None = None
    captured_at: str | None = None
    raw: dict = Field(default_factory=dict)


class XhsSearchEvidence(BaseModel):
    """Search evidence JSON produced by local RPA or provider mocks."""

    job_id: str | None = None
    task_type: str | None = "xhs_keyword_search"
    status: str | None = None
    keyword: str | None = None
    account_id: str | None = None
    provider_type: str | None = None
    captured_at: str | None = None
    screenshot_path: str | None = None
    evidence_json_path: str | None = None
    result_area_found: bool | None = None
    item_count: int | None = None
    normalized_record_count: int | None = None
    items: list[XhsSearchItem] = Field(default_factory=list)
    normalized_records: list[XhsNormalizedRecord] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None


class XhsKeywordTask(BaseModel):
    """One keyword task inside a batch request."""

    keyword: str
    account_id: str
    provider_type: str
    limit: int = 20
    job_id: str | None = None


class XhsBatchKeywordRequest(BaseModel):
    """Batch keyword search request."""

    batch_id: str
    account_id: str
    provider_type: str
    keywords: list[str]
    limit: int = 20
    mode: Literal["sync", "async"] = "sync"
    evidence_root: str | None = None


class XhsBatchKeywordResult(BaseModel):
    """Batch keyword search summary."""

    batch_id: str
    status: str
    total_keywords: int
    success_count: int
    failed_count: int
    jobs: list[dict] = Field(default_factory=list)
    created_at: str
    finished_at: str | None = None

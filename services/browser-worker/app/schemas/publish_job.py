from pydantic import BaseModel


class PublishJob(BaseModel):
    """Payload for a browser-worker publish job."""

    job_id: str
    feishu_record_id: str | None = None
    account_id: str
    provider_type: str = "selenium_chrome"
    title: str
    body: str
    tags: list[str]
    images: list[str]
    publish_mode: str = "now"
    scheduled_at: str | None = None

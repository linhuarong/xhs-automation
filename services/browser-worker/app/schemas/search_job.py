from pydantic import BaseModel


class SearchJob(BaseModel):
    """Payload for a browser-worker search job."""

    job_id: str
    feishu_record_id: str | None = None
    account_id: str
    provider_type: str = "selenium_chrome"
    keyword: str
    keyword_type: str | None = None
    limit: int = 20
    capture_screenshot: bool = True

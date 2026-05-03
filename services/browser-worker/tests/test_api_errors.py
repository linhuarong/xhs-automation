from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_get_publish_job_not_exists_returns_404() -> None:
    response = client.get("/api/xhs/publish/not-exists")

    assert response.status_code == 404
    assert response.json() == {"detail": "job not found"}


def test_search_missing_keyword_returns_422() -> None:
    response = client.post(
        "/api/xhs/search",
        json={
            "job_id": "search-error-1",
            "account_id": "xhs_dev_01",
        },
    )

    assert response.status_code == 422


def test_publish_missing_title_returns_422() -> None:
    response = client.post(
        "/api/xhs/publish",
        json={
            "job_id": "publish-error-1",
            "account_id": "xhs_dev_01",
            "body": "test body",
            "tags": ["test"],
            "images": [],
        },
    )

    assert response.status_code == 422

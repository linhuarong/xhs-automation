from fastapi import FastAPI

from app.api import publish_router, search_router


SERVICE_NAME = "xhs-browser-worker"
VERSION = "0.1.0"

app = FastAPI(title=SERVICE_NAME, version=VERSION)
app.include_router(search_router)
app.include_router(publish_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": VERSION,
    }

from fastapi import FastAPI


SERVICE_NAME = "xhs-browser-worker"
VERSION = "0.1.0"

app = FastAPI(title=SERVICE_NAME, version=VERSION)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": VERSION,
    }

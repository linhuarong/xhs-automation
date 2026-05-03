# xhs-browser-worker

FastAPI skeleton for the browser-worker service.

This service currently provides the minimal FastAPI shell, health check, schemas, and a local development Chrome provider. It does not implement XHS page automation, publishing, search, Feishu, MinIO, or PostgreSQL integration.

## Local Setup

Create and activate a virtual environment, then install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Start

Run the service from this directory:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Health Check

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "xhs-browser-worker",
  "version": "0.1.0"
}
```

## API Smoke Test

Start the service first. The smoke test script only checks the already-running local service and does not start Uvicorn.

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

In another PowerShell window, run:

```powershell
.\scripts\smoke_test.ps1
```

The script checks:

- `GET /health`
- `POST /api/xhs/search`
- `POST /api/xhs/publish`
- `GET /api/xhs/publish/publish-smoke-1`

Expected final output:

```text
browser-worker smoke test passed
```

## Pytest

Install dependencies, then run tests from the `services/browser-worker` directory:

```powershell
pip install -r requirements.txt
pytest
```

The pytest suite covers the health endpoint, schema defaults, `WorkerResult`, and the in-memory job registry. It does not start Chrome, execute Selenium, visit XHS, or call external services.

## Image Download Service

`download_images(job_id, image_urls, download_root=".local_downloads")` downloads HTTP/HTTPS image URLs into a local job directory:

```text
{download_root}/{job_id}/
```

Files are named with a stable sequence prefix, such as `001_image.png`. If a URL has no filename, the downloader uses `001_image`.

Example:

```powershell
python -c "from app.services.image_downloader import download_images; print(download_images('manual-test', ['https://example.com/image.png']))"
```

Local downloads are ignored by Git under `.local_downloads/`. This service does not upload to MinIO or call Feishu/PostgreSQL.

## Browser Utility Layer

The browser-worker includes small browser utility helpers that operate only on caller-provided driver or element objects:

- `save_screenshot(driver, job_id, name)` saves `{screenshot_root}/{job_id}/{name}.png` locally and does not upload to MinIO.
- `upload_files_to_input(file_input, file_paths)` validates local paths and sends newline-joined paths to a file input via `send_keys`.
- `clear_and_type(element, text)` clears an element and types text via `send_keys`.
- `safe_type(element, text)` uses `clear + send_keys` when available, with a `click + send_keys` fallback.

These helpers do not open websites, use the clipboard, operate OS file picker dialogs, or make network requests.

## Local Chrome Provider Smoke Test

The Selenium Chrome provider is only for local development debugging. It starts a normal local Chrome profile, does not open XHS, and does not visit any external website.

Run this from the `services/browser-worker` directory after installing dependencies:

```powershell
python -c "from app.providers import SeleniumChromeProvider; provider = SeleniumChromeProvider(); session = provider.open_profile('local-dev'); print(session); print(provider.check_login(provider.get_driver(session))); provider.close_profile(session)"
```

To capture a local screenshot of the initial Chrome window:

```powershell
python -c "from app.providers import SeleniumChromeProvider; provider = SeleniumChromeProvider(); session = provider.open_profile('local-dev'); print(provider.capture_screenshot(session, 'smoke')); provider.close_profile(session)"
```

Local Chrome profile data is written under `.local_profiles/{account_id}` by default. Local screenshots are written under `.local_screenshots/{session_id}/{name}.png` by default.

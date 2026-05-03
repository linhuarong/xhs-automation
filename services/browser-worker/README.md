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

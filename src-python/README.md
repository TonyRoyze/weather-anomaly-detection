# Anomalize FastAPI Backend

This folder contains the FastAPI backend used by the Anomalize frontend.

It is responsible for:

- weather and forecast API responses
- prediction metadata for supported cities and date ranges
- anomaly scoring and category prediction (lightweight runtime)

## Important Files

- `main.py` starts the FastAPI app
- `api/endpoints.py` defines the HTTP routes
- `api/services/open_meteo.py` contains the Open-Meteo integration
- `requirements.txt` lists the Python dependencies
- `requirements-dev.txt` contains the heavier ML stack for local experimentation only
- `models-lite/` contains the lightweight, deployable XGBoost artifacts

## Run Locally

### 1. Move to the project root

The backend is usually started from the repo root, not from inside `src-python/`.

```bash
cd /path/to/Anomalize
```

### 2. Create and activate a virtual environment

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r src-python/requirements.txt
```

### 4. Start the API server

From the repo root:

```bash
uvicorn main:app --reload --app-dir src-python
```

Or use the matching frontend script:

```bash
pnpm run dev:api
```

## What To Run With It

To use the full app locally, also start the frontend in a second terminal:

```bash
pnpm run dev
```

## Notes

- Auto-reload is enabled in local development.
- The API serves the dashboard and forecast pages used by the SvelteKit frontend.
- For Vercel deployments, the backend runs inference with only `xgboost` + `numpy` using artifacts in `src-python/models-lite`.

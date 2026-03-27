# Anomalize

Anomalize is a weather analytics workspace built with SvelteKit for the UI and FastAPI for the prediction API. It combines a historical Sri Lanka weather dataset with live forecast data so you can:

- explore the bundled dataset by city and date range
- score dates for anomaly likelihood
- inspect forecast timelines, alerts, and 5-day operational outlooks

The repository also contains a Tauri shell in `src-tauri/`, but the fastest way to run the project locally today is as a web frontend plus Python API.

## Stack

- SvelteKit 5 + TypeScript
- Tailwind CSS
- FastAPI + Uvicorn
- pandas, scikit-learn, imbalanced-learn, XGBoost
- Rust/Tauri shell files in `src-tauri/`

## Project Structure

```text
.
├── src/                            # SvelteKit app
│   ├── routes/                     # Landing page, dashboard pages, API routes
│   ├── lib/components/             # Shared UI and dashboard components
│   └── SriLanka_Weather_Dataset_V1.csv
├── src-python/                     # FastAPI app and weather/prediction services
├── src-tauri/                      # Tauri desktop shell
├── package.json                    # Frontend scripts
└── README.md
```

## Prerequisites

Install these before starting:

- Node.js 18+ 
- `pnpm`
- Python 3.10+ recommended
- `pip`

Optional if you want to work on the desktop shell later:

- Rust via `rustup`
- platform dependencies required by Tauri

## Run Locally

### 1. Install frontend dependencies

From the project root:

```bash
pnpm install
```

### 2. Create a Python virtual environment

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

### 3. Install Python dependencies

With the virtual environment activated:

```bash
pip install -r src-python/requirements.txt
```

### 4. Start the FastAPI backend

In one terminal, from the project root:

```bash
source .venv/bin/activate
pnpm run dev:api
```

That starts the API with auto-reload using the app in `src-python/main.py`.

### 5. Start the SvelteKit frontend

In a second terminal, from the project root:

```bash
pnpm run dev
```

### 6. Open the app in your browser

Vite will print the local URL in the terminal, usually:

```text
http://localhost:5173
```

From there you can access:

- `/` for the landing page
- `/dashboard` for anomaly prediction
- `/dashboard/dataset` for dataset browsing
- `/downloads` for the downloads page

## Step-by-Step Daily Workflow

If you are returning to the project later, this is the shortest path:

1. Open a terminal in the repo.
2. Activate the Python environment: `source .venv/bin/activate`
3. Start the API: `pnpm run dev:api`
4. Open a second terminal.
5. Start the frontend: `pnpm run dev`
6. Visit the local Vite URL shown in the terminal.

## Useful Commands

```bash
pnpm run dev         # Start the frontend
pnpm run dev:api     # Start the FastAPI backend
pnpm run build       # Build the frontend
pnpm run preview     # Preview the production frontend build
pnpm run check       # Run Svelte type + diagnostics checks
```

## Backend Notes

- The backend entry point is `src-python/main.py`.
- Weather routes and prediction endpoints live under `src-python/api/`.
- The historical dataset used by the UI is bundled at `src/SriLanka_Weather_Dataset_V1.csv`.

## Troubleshooting

### `pnpm: command not found`

Install pnpm first:

```bash
npm install -g pnpm
```

### `uvicorn: command not found`

Your virtual environment is probably not active, or the Python dependencies are not installed yet:

```bash
source .venv/bin/activate
pip install -r src-python/requirements.txt
```

### Frontend loads but predictions fail

Make sure the FastAPI server is running in a separate terminal with:

```bash
pnpm run dev:api
```

## Tauri

This repository includes a Tauri shell under `src-tauri/`, but the README above documents the currently reliable local workflow based on the frontend and Python API scripts already present in `package.json`.

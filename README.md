# Anomalize

Anomalize is a weather analytics application designed for identifying anomalies from historical and live weather data.

It features a native **Rust-based inference engine** using ONNX Runtime.

- **Explore** weather datasets for specific cities and date ranges.
- **Predict** 5-day anomaly risks using machine learning models.
- **Visualize** forecast timelines with interactive charts and confidence bands.
- **Native Experience** via a Tauri desktop shell (macOS DMG available).

## Key Features

- **Native ML Inference**: In-process model scoring via Rust + ONNX Runtime (`ort`).
- **5-Day Prediction Horizon**: Automated daily scoring of future forecasts using the Open-Meteo API.
- **Dynamic Visuals**: interactive time-series charts powered by `layerchart` and `d3`.
- **Flexible Modes**: Toggle between Conservative (XGBoost) and Sensitive (Random Forest) anomaly scoring modes.
- **Resilient Feed**: Automatic fallback between historical archive and live forecast APIs for continuous data availability.

## Tech Stack

- **Frontend**: SvelteKit 5, TypeScript, Tailwind CSS
- **Visualizations**: LayerChart, D3.js
- **Backend (Desktop)**: Rust, Tauri v2
- **Inference Engine**: ONNX Runtime (`ort` crate), ndarray
- **Local API**: Axum, Tokio, Reqwest
- **Data Training**: Python, scikit-learn, XGBoost (models exported to ONNX)

## Project Structure

```text
.
├── src/                        # SvelteKit App (shadcn UI, layerchart components)
│   ├── lib/                    # Shared logic, API clients, and chart wrappers
│   └── routes/                 # Dashboard, landing, and analytics routes
├── src-tauri/                  # Native Rust Workspace
│   ├── src/                    # ONNX inference handlers, Axum server, and Tauri commands
│   └── Cargo.toml              # Rust dependency manifest
├── src-python/                 # Training & Export Utilities (not required for runtime)
│   ├── export_onnx.py          # Script to convert trained pipelines to ONNX
│   └── weather_models/         # Binary models and preprocessors (ONNX files)
└── README.md
```

## Getting Started

### Prerequisites

- **Rust**: [rustup.rs](https://rustup.rs/) (required for native backend)
- **Node.js**: 18+ (pnpm recommended)
- **Tauri dependencies**: See [Tauri Prerequisites](https://v2.tauri.app/start/prerequisites/) for your OS.

### Installation

**Direct Download (macOS)**:
Run the included `.dmg` installer to get started immediately without setting up a development environment.

**Quick Start (macOS/Linux)**:
Use the automated bootstrap script to clone the repository, check dependencies, and install all requirements in one command:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/TonyRoyze/weather-anomaly-detection/main/bootstrap.sh)"
```

**Quick Start (Windows)**:
Open PowerShell as Administrator and run the following command:
```powershell
irm https://raw.githubusercontent.com/TonyRoyze/weather-anomaly-detection/main/bootstrap.ps1 | iex
```

**Manual Setup**:
1. Clone the repository and install frontend dependencies:
   ```bash
   pnpm install
   ```

2. Run in **Desktop Mode** (Native Rust + Svelte):
   ```bash
   # On macOS/Linux: ./run.sh
   # On Windows (PowerShell): .\run.ps1
   ```

3. Run in **Web Mode** (Python API + Svelte):
   ```bash
   # On macOS/Linux: ./web_dev.sh
   # On Windows (PowerShell): .\web_dev.ps1
   ```

4. Run the **Frontend Only** (Vite):
   ```bash
   pnpm run dev
   ```

### Running with a Python fallback (Optional)

If you prefer to run the project as a standard web application without Tauri, you can still use the legacy Python FastAPI backend located in `src-python/`.

1. Setup the Python environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r src-python/requirements.txt
   ```

2. Start the API and Frontend separately:
   ```bash
   pnpm run dev:api
   pnpm run dev
   ```

## ML Models

Anomalize utilizes two primary pipelines for its 5-day predictive horizon:

1. **Anomaly Scoring**: Binary classification scoring for the likelihood of a given day being "out of band" based on historical baselines.
2. **Category Classification**: Multiclass prediction to identify the dominant signal (Heatwave, Precipitation Spike, Wind Surge) if an anomaly is detected.

The models are trained on a comprehensive historical weather dataset for Sri Lanka and exported to ONNX format for efficient cross-platform execution.

## License

MIT

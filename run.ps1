# Anomalize Development Server Runner (Windows)
# Starts the SvelteKit frontend and native Rust backend via Tauri.

if (-not (Test-Path "package.json")) {
    Write-Host "Error: Please run this script from the project root directory." -ForegroundColor Red
    exit
}

Write-Host "🚀 Starting Anomalize (Desktop Mode)..." -ForegroundColor Blue
pnpm tauri dev

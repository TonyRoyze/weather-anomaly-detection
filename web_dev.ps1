# Anomalize Web-Only Dev Runner (Windows)
# Starts the SvelteKit frontend and the Python FastAPI backend in parallel.

if (Test-Path ".venv\Scripts\Activate.ps1") {
    . ".venv\Scripts\Activate.ps1"
    Write-Host "✓ Activated Python virtual environment." -ForegroundColor Green
} else {
    Write-Host "⚠️  Warning: No .venv found. Python API might fail." -ForegroundColor Yellow
}

Write-Host "🚀 Starting Anomalize Web Stack..." -ForegroundColor Blue
pnpm dlx concurrently -n "api,svelte" -c "blue,green" `
    "pnpm run dev:api" `
    "pnpm run dev"

#!/bin/bash

# Anomalize Web-Only Dev Runner
# Starts the SvelteKit frontend and the Python FastAPI backend in parallel.

if [[ -z "$VIRTUAL_ENV" ]]; then
    if [ -d ".venv" ]; then
        source .venv/bin/activate
        echo "✓ Activated Python virtual environment."
    else
        echo "⚠️  Warning: No .venv found. Python API might fail."
    fi
fi

echo "🚀 Starting Anomalize Web Stack..."
pnpm dlx concurrently -n "api,svelte" -c "blue,green" \
    "pnpm run dev:api" \
    "pnpm run dev"

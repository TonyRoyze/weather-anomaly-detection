#!/bin/bash

# Anomalize Development Server Runner
# Starts the SvelteKit frontend and native Rust backend via Tauri.

# Ensure we're in the right directory
if [ ! -f "package.json" ]; then
    echo "Error: Please run this script from the project root directory."
    exit 1
fi

echo "🚀 Starting Anomalize (Desktop Mode)..."
pnpm tauri dev

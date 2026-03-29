# Anomalize Windows Setup Script
# Automatically ensures all prerequisites are installed and pnpm is ready.

$REPO_URL = "https://github.com/TonyRoyze/weather-anomaly-detection.git"
$PROJECT_DIR = "weather-anomaly-detection"

Write-Host "🚀 Beginning Anomalize Windows setup..." -ForegroundColor Blue

# Check for Git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Git not found. Installing via winget..." -ForegroundColor Yellow
    winget install --id Git.Git -e --source winget
} else {
    Write-Host "✓ Git is installed." -ForegroundColor Green
}

# Clone the repository
if (-not (Test-Path $PROJECT_DIR)) {
    Write-Host "Cloning repository..." -ForegroundColor Blue
    git clone $REPO_URL
    Set-Location $PROJECT_DIR
} else {
    Write-Host "✓ Project directory '$PROJECT_DIR' already exists." -ForegroundColor Green
    Set-Location $PROJECT_DIR
}

# 1. Ensure Node.js is installed
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "Node.js not found. Installing via winget..." -ForegroundColor Yellow
    winget install -e --id OpenJS.NodeJS.LTS
} else {
    Write-Host "✓ Node.js $(node -v) is installed." -ForegroundColor Green
}

# 2. Ensure pnpm is installed
if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
    Write-Host "pnpm not found. Installing pnpm..." -ForegroundColor Yellow
    iwr https://get.pnpm.io/install.ps1 -useb | iex
} else {
    Write-Host "✓ pnpm $(pnpm -v) is installed." -ForegroundColor Green
}

# 3. Ensure Rust toolchain is installed
if (-not (Get-Command rustc -ErrorAction SilentlyContinue)) {
    Write-Host "Rust not found. Installing Rust via rustup-init..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri "https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe" -OutFile "$env:TEMP\rustup-init.exe"
    & "$env:TEMP\rustup-init.exe" -y
    $env:Path += ";$env:USERPROFILE\.cargo\bin"
} else {
    Write-Host "✓ Rust $(rustc --version | Select-String -Pattern '\d+\.\d+\.\d+' | % { $_.Matches.Value }) is installed." -ForegroundColor Green
}

# 4. Tauri Windows prereqs (WebView2 should be present on Win10/11)
# Note: C++ Build tools are required but best handled by manual installation from Microsoft 
Write-Host "⚠️  Note: Anomalize requires 'C++ build tools' for Rust/Tauri compile." -ForegroundColor Yellow
Write-Host "If build fails, download them here: https://visualstudio.microsoft.com/visual-cpp-build-tools/" -ForegroundColor Blue

# Install project dependencies
Write-Host "Installing frontend dependencies..." -ForegroundColor Blue
pnpm install

Write-Host "`n✨ Anomalize setup is complete!" -ForegroundColor Green
Write-Host "----------------------------------------"
Write-Host "To start the development environment, run:"
Write-Host "pnpm tauri dev" -ForegroundColor Blue
Write-Host "----------------------------------------"

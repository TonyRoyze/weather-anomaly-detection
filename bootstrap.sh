#!/bin/bash

# Anomalize Setup Script
# Automatically clones the repository and ensures all dependencies are installed.

REPO_URL="https://github.com/TonyRoyze/weather-anomaly-detection.git"
PROJECT_DIR="weather-anomaly-detection"

# Color constants for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Beginning Anomalize setup...${NC}"

# Ensure Homebrew is available (macOS primary dependency manager)
if ! command -v brew &> /dev/null; then
    echo -e "${RED}Homebrew not found.${NC} Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add brew to PATH for the current session if it was just installed
    if [[ "$OSTYPE" == "darwin"* ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    echo -e "${GREEN}✓ Homebrew is already installed.${NC}"
fi

# Clone the repository if it doesn't already exist
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${BLUE}Cloning repository...${NC}"
    git clone "$REPO_URL"
    cd "$PROJECT_DIR" || exit
else
    echo -e "${GREEN}✓ Project directory '$PROJECT_DIR' already exists.${NC}"
    cd "$PROJECT_DIR" || exit
fi

# 1. Ensure Node.js is installed
if ! command -v node &> /dev/null; then
    echo -e "${RED}Node.js not found.${NC} Installing Node.js via Homebrew..."
    brew install node
else
    NODE_VERSION=$(node -v | cut -d 'v' -f 2 | cut -d '.' -f 1)
    if [ "$NODE_VERSION" -lt 18 ]; then
        echo -e "${RED}Node.js version is too low ($NODE_VERSION).${NC} Updating to latest..."
        brew upgrade node
    else
        echo -e "${GREEN}✓ Node.js $(node -v) is installed.${NC}"
    fi
fi

# 2. Ensure pnpm is installed
if ! command -v pnpm &> /dev/null; then
    echo -e "${RED}pnpm not found.${NC} Installing pnpm..."
    brew install pnpm
else
    echo -e "${GREEN}✓ pnpm $(pnpm -v) is installed.${NC}"
fi

# 3. Ensure Rust toolchain is installed
if ! command -v rustc &> /dev/null; then
    echo -e "${RED}Rust not found.${NC} Installing Rust via rustup..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
else
    echo -e "${GREEN}✓ Rust $(rustc --version | cut -d ' ' -f 2) is installed.${NC}"
fi

# 4. Check for macOS SDK / Command Line Tools
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! xcode-select -p &> /dev/null; then
        echo -e "${RED}Xcode Command Line Tools not found.${NC} Installing..."
        xcode-select --install
        echo -e "${BLUE}Please complete the Xcode tools installation manually before proceeding.${NC}"
        exit 1
    else
        echo -e "${GREEN}✓ Xcode Command Line Tools are present.${NC}"
    fi
fi

# Install project dependencies
echo -e "${BLUE}Installing frontend dependencies...${NC}"
pnpm install

echo -e "\n${GREEN}✨ Anomalize setup is complete!${NC}"
echo -e "----------------------------------------"
echo -e "To start the development environment, run:"
echo -e "${BLUE}pnpm tauri dev${NC}"
echo -e "----------------------------------------"

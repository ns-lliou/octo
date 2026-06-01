#!/usr/bin/env bash

set -e

APP_ENTRY="src/Home.py"
VENV_DIR=".venv"

echo "========================================"
echo " Starting Octo"
echo "========================================"

# Move to script directory so the script works from any current path
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Pick Python command — prefer versioned executables to avoid system Python
PYTHON_CMD=""
for cmd in python3.12 python3.11 python3.10 python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PYTHON_CMD="$cmd"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "ERROR: Python is not installed or not found in PATH."
    exit 1
fi

echo "Using Python: $($PYTHON_CMD --version)"

# Enforce minimum Python version (3.10+ required for union type syntax)
PYTHON_VERSION=$("$PYTHON_CMD" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]; }; then
    echo "ERROR: Python 3.10 or higher is required (found $PYTHON_VERSION). Install it via Homebrew: brew install python@3.12"
    exit 1
fi

# Create venv if missing
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment: $VENV_DIR"
    "$PYTHON_CMD" -m venv "$VENV_DIR"
fi

# Activate venv
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip

# Install dependencies
if [ -f "requirements.txt" ]; then
    echo "Installing dependencies from requirements.txt..."
    pip install -r requirements.txt
else
    echo "WARNING: requirements.txt not found. Skipping dependency installation."
fi

# Install internal Netskope packages (requires Artifactory access)
if [ -f "requirements_local.txt" ]; then
    echo "Installing internal dependencies from requirements_local.txt..."
    pip install --no-cache-dir -r requirements_local.txt \
        --index-url https://artifactory-rd.netskope.io/artifactory/api/pypi/ns-pypi/simple \
        || echo "WARNING: Failed to install requirements_local.txt — skipping (may not be on Netskope network)"
fi

# Validate app entry
if [ ! -f "$APP_ENTRY" ]; then
    echo "ERROR: Cannot find $APP_ENTRY"
    exit 1
fi

echo "Launching Octo Streamlit app..."
echo "Open the URL shown by Streamlit in your browser."
echo "========================================"

python -m streamlit run "$APP_ENTRY"

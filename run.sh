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

# Pick Python command
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "ERROR: Python is not installed or not found in PATH."
    exit 1
fi

echo "Using Python: $($PYTHON_CMD --version)"

# Enforce minimum Python version (3.10+ required for union type syntax)
PYTHON_VERSION=$("$PYTHON_CMD" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]; }; then
    echo "ERROR: Python 3.10 or higher is required (found $PYTHON_VERSION)."
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

# Validate app entry
if [ ! -f "$APP_ENTRY" ]; then
    echo "ERROR: Cannot find $APP_ENTRY"
    exit 1
fi

echo "Launching Octo Streamlit app..."
echo "Open the URL shown by Streamlit in your browser."
echo "========================================"

python -m streamlit run "$APP_ENTRY"

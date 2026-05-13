$ErrorActionPreference = "Stop"

$AppEntry = "src/Home.py"
$VenvDir = ".venv"

Write-Host "========================================"
Write-Host " Starting Octo"
Write-Host "========================================"

# Move to script directory so the script works from any current path
Set-Location $PSScriptRoot

# Pick Python command
$PythonCmd = $null

if (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCmd = "python"
}
elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCmd = "py"
}
else {
    Write-Host "ERROR: Python is not installed or not found in PATH."
    exit 1
}

Write-Host "Using Python:"
& $PythonCmd --version

# Create venv if missing
if (-Not (Test-Path $VenvDir)) {
    Write-Host "Creating virtual environment: $VenvDir"
    & $PythonCmd -m venv $VenvDir
}

# Activate venv
$ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"

if (-Not (Test-Path $ActivateScript)) {
    Write-Host "ERROR: Cannot find virtual environment activation script: $ActivateScript"
    exit 1
}

Write-Host "Activating virtual environment..."
. $ActivateScript

# Upgrade pip
Write-Host "Upgrading pip..."
python -m pip install --upgrade pip

# Install dependencies
if (Test-Path "requirements.txt") {
    Write-Host "Installing dependencies from requirements.txt..."
    pip install -r requirements.txt
}
else {
    Write-Host "WARNING: requirements.txt not found. Skipping dependency installation."
}

# Validate app entry
if (-Not (Test-Path $AppEntry)) {
    Write-Host "ERROR: Cannot find $AppEntry"
    exit 1
}

Write-Host "Launching Octo Streamlit app..."
Write-Host "Open the URL shown by Streamlit in your browser."
Write-Host "========================================"

python -m streamlit run $AppEntry
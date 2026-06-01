$ErrorActionPreference = "Stop"

$AppEntry = "src/Home.py"
$VenvDir = ".venv"

Write-Host "========================================"
Write-Host " Starting Octo"
Write-Host "========================================"

# Move to script directory so the script works from any current path
Set-Location $PSScriptRoot

# Pick Python command — prefer versioned executables to avoid system Python
$PythonCmd = $null

foreach ($cmd in @("python3.12", "python3.11", "python3.10", "python3", "python", "py")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        try {
            $testOutput = & $cmd -c "import sys; print(sys.version_info.major)" 2>$null
            if ($testOutput -match '^\d+$') {
                $PythonCmd = $cmd
                break
            }
        } catch {
            # stub or non-functional executable, skip
        }
    }
}

if ($null -eq $PythonCmd) {
    Write-Host "ERROR: Python is not installed or not found in PATH."
    exit 1
}

Write-Host "Using Python:"
& $PythonCmd --version

# Enforce minimum Python version (3.10+ required for union type syntax)
$PythonVersion = & $PythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$VersionParts = $PythonVersion.Split('.')
$Major = [int]$VersionParts[0]
$Minor = [int]$VersionParts[1]
if ($Major -lt 3 -or ($Major -eq 3 -and $Minor -lt 10)) {
    Write-Host "ERROR: Python 3.10 or higher is required (found $PythonVersion). Install it from https://www.python.org/downloads/"
    exit 1
}

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

# Install internal Netskope packages (requires Artifactory access)
if (Test-Path "requirements_local.txt") {
    Write-Host "Installing internal dependencies from requirements_local.txt..."
    try {
        pip install --no-cache-dir -r requirements_local.txt `
            --index-url https://artifactory-rd.netskope.io/artifactory/api/pypi/ns-pypi/simple
    } catch {
        Write-Host "WARNING: Failed to install requirements_local.txt — skipping (may not be on Netskope network)"
    }
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
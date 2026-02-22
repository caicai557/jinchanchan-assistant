# Windows PyInstaller Build Script (PowerShell)
# Usage: .\scripts\build_win.ps1 [-Clean]

param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$BuildDir = Join-Path $ProjectRoot "build"
$DistDir = Join-Path $ProjectRoot "dist"

function Log-Info { Write-Host "[INFO] $args" -ForegroundColor Green }
function Log-Warn { Write-Host "[WARN] $args" -ForegroundColor Yellow }
function Log-Error { Write-Host "[ERROR] $args" -ForegroundColor Red }

Set-Location $ProjectRoot

# Clean old build
if ($Clean) {
    Log-Info "Cleaning old build..."
    if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }
    if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir }
}

# Check virtual environment
$VenvPython = Join-Path $ProjectRoot "venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Log-Error "Virtual environment not found."
    Log-Error "Please run: python -m venv venv"
    Log-Error "Then run: .\venv\Scripts\pip install -e .[dev,control,windows]"
    exit 1
}

# Install PyInstaller
Log-Info "Checking PyInstaller..."
& $VenvPython -m pip install "pyinstaller>=6.0.0" "pyyaml" -q

# Run lint checks
Log-Info "Running lint checks..."
& $VenvPython -m ruff check .
if ($LASTEXITCODE -ne 0) { Log-Error "ruff check failed"; exit 1 }
& $VenvPython -m mypy .
if ($LASTEXITCODE -ne 0) { Log-Error "mypy failed"; exit 1 }
& $VenvPython -m pytest -q
if ($LASTEXITCODE -ne 0) { Log-Error "pytest failed"; exit 1 }
Log-Info "Lint checks passed"

# Run PyInstaller
Log-Info "Building with PyInstaller..."
$TemplatesPath = "resources/templates;resources/templates"
$GameDataPath = "resources/game_data;resources/game_data"
$ConfigPath = "config/config.example.yaml;config"

& $VenvPython -m PyInstaller `
    --name "jinchanchan-assistant" `
    --onefile `
    --console `
    --add-data $TemplatesPath `
    --add-data $GameDataPath `
    --add-data $ConfigPath `
    --hidden-import "yaml" `
    --hidden-import "PIL" `
    --hidden-import "pydantic" `
    --hidden-import "mss" `
    --hidden-import "numpy" `
    --hidden-import "rich" `
    --hidden-import "rich.console" `
    --hidden-import "rich.layout" `
    --hidden-import "rich.live" `
    --hidden-import "rich.panel" `
    --hidden-import "rich.table" `
    --hidden-import "rich.text" `
    --collect-all "rich" `
    --exclude-module "cv2" `
    --exclude-module "onnxruntime" `
    --exclude-module "rapidocr_onnxruntime" `
    --exclude-module "anthropic" `
    --exclude-module "openai" `
    --exclude-module "google.genai" `
    --exclude-module "pyobjc" `
    --exclude-module "Quartz" `
    --noupx `
    --noconfirm `
    main.py

if ($LASTEXITCODE -ne 0) {
    Log-Error "PyInstaller build failed"
    exit 1
}

# Check output
$ExePath = Join-Path $DistDir "jinchanchan-assistant.exe"
if (-not (Test-Path $ExePath)) {
    Log-Error "Build failed, output not found"
    exit 1
}

Log-Info "Build successful"
Log-Info "Output: $ExePath"

# Run smoke tests
Log-Info "Running smoke tests on build..."
$SmokeFailed = $false

# --help
& $ExePath --help 2>&1 | Out-Null
$HelpExit = $LASTEXITCODE
if ($HelpExit -eq 0) {
    Log-Info "  --help OK"
} else {
    Log-Error "  --help FAILED (exit: $HelpExit)"
    $SmokeFailed = $true
}

# --version
$VersionOutput = & $ExePath --version 2>&1
$VersionExit = $LASTEXITCODE
if ($VersionExit -eq 0) {
    Log-Info "  --version: $VersionOutput"
} else {
    Log-Error "  --version FAILED (exit: $VersionExit)"
    $SmokeFailed = $true
}

# --dry-run (may fail without device, that's OK)
& $ExePath --platform windows --dry-run --llm-provider none 2>&1 | Out-Null
$DryRunExit = $LASTEXITCODE
# dry-run exit code is not critical, just log it
Log-Info "  --dry-run completed (exit: $DryRunExit)"

# Final result
if ($SmokeFailed) {
    Log-Error "Smoke tests FAILED"
    exit 1
}

Log-Info "Smoke tests PASSED"
Log-Info "Build finished"
exit 0

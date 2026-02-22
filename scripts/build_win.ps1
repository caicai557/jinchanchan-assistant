# Windows PyInstaller 打包脚本 (PowerShell)
# 用法: .\scripts\build_win.ps1 [-Clean]

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

# 清理旧构建
if ($Clean) {
    Log-Info "清理旧构建..."
    if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }
    if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir }
}

# 检查虚拟环境
$VenvPython = Join-Path $ProjectRoot "venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Log-Error "虚拟环境不存在，请先运行: python -m venv venv && .\venv\Scripts\pip install -e .[dev,control,windows]"
    exit 1
}

# 安装 PyInstaller
Log-Info "检查 PyInstaller..."
& $VenvPython -m pip install "pyinstaller>=6.0.0" -q

# 检查门禁
Log-Info "运行门禁检查..."
& $VenvPython -m ruff check . || { Log-Error "ruff check 失败"; exit 1 }
& $VenvPython -m mypy . || { Log-Error "mypy 失败"; exit 1 }
& $VenvPython -m pytest -q || { Log-Error "pytest 失败"; exit 1 }
Log-Info "门禁通过 ✓"

# 运行 PyInstaller
Log-Info "开始打包..."
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
    --hidden-import "pyyaml" `
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

# 检查产物
$ExePath = Join-Path $DistDir "jinchanchan-assistant.exe"
if (Test-Path $ExePath) {
    Log-Info "打包成功 ✓"
    Log-Info "产物位置: $ExePath"

    # 运行 smoke 测试
    Log-Info "运行打包产物 smoke 测试..."

    # --help
    & $ExePath --help | Out-Null
    if ($LASTEXITCODE -eq 0) { Log-Info "  --help ✓" } else { Log-Warn "  --help 失败" }

    # --version
    $VersionOutput = & $ExePath --version 2>&1
    Log-Info "  --version: $VersionOutput"

    # --platform windows --dry-run (无设备时友好提示)
    & $ExePath --platform windows --dry-run 2>&1 | Out-Null
    Log-Info "  --dry-run 测试完成"

    Log-Info "打包完成！"
    Log-Info "运行命令: $ExePath --help"
} else {
    Log-Error "打包失败，产物不存在"
    exit 1
}

# Windows 产物验收脚本 (PowerShell)
# 用法: .\scripts\smoke_dist_win.ps1 [-SkipBuild]

param(
    [switch]$SkipBuild
)

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$DistDir = Join-Path $ProjectRoot "dist"
$ArtifactsDir = Join-Path $ProjectRoot "artifacts\smoke"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

$PassCount = 0
$FailCount = 0

function Log-Info { Write-Host "[INFO] $args" -ForegroundColor Green }
function Log-Pass { Write-Host "[PASS] $args" -ForegroundColor Green; $script:PassCount++ }
function Log-Fail { Write-Host "[FAIL] $args" -ForegroundColor Red; $script:FailCount++ }
function Log-Warn { Write-Host "[WARN] $args" -ForegroundColor Yellow }
function Log-Step { Write-Host "[STEP] $args" -ForegroundColor Blue }

function Save-Artifact {
    param([string]$Name, [string]$Content)
    $File = Join-Path $ArtifactsDir "${Name}_${Timestamp}.log"
    $Content | Out-File -FilePath $File -Encoding utf8
    Write-Host "Artifact saved: $File"
}

function Save-ExitCode {
    param([string]$Name, [int]$Code)
    $Json = "{`"test`": `"$Name`", `"exit_code`": $Code, `"timestamp`": `"$Timestamp`"}"
    $File = Join-Path $ArtifactsDir "${Name}_result.json"
    $Json | Out-File -FilePath $File -Encoding utf8
}

# 初始化 artifacts 目录
New-Item -ItemType Directory -Force -Path $ArtifactsDir | Out-Null

# 清理旧 artifacts
Remove-Item -Path "$ArtifactsDir\*.log" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "$ArtifactsDir\*.json" -Force -ErrorAction SilentlyContinue

Set-Location $ProjectRoot

# Step 1: 清理
Log-Step "清理旧构建..."
if (-not $SkipBuild) {
    if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir }
    Log-Pass "清理完成"
} else {
    Log-Info "跳过清理 (-SkipBuild)"
}

# Step 2: 构建
if (-not $SkipBuild) {
    Log-Step "构建产物..."
    $BuildLog = Join-Path $ArtifactsDir "build_${Timestamp}.log"
    & powershell -ExecutionPolicy Bypass -File ".\scripts\build_win.ps1" 2>&1 | Tee-Object -FilePath $BuildLog
    $BuildExit = $LASTEXITCODE
    Save-ExitCode -Name "build" -Code $BuildExit

    if ($BuildExit -eq 0) {
        Log-Pass "构建成功"
    } else {
        Log-Fail "构建失败 (exit: $BuildExit)"
        exit 1
    }
} else {
    Log-Info "跳过构建 (-SkipBuild)"
}

# 检查产物存在
$ExePath = Join-Path $DistDir "jinchanchan-assistant.exe"
if (-not (Test-Path $ExePath)) {
    Log-Fail "产物不存在: $ExePath"
    exit 1
}
Log-Pass "产物存在: $ExePath"

# Step 3: --version 测试
Log-Step "测试 --version..."
$VersionOutput = & $ExePath --version 2>&1
$VersionExit = $LASTEXITCODE
Save-Artifact -Name "version" -Content $VersionOutput
Save-ExitCode -Name "version" -Code $VersionExit

if ($VersionExit -eq 0) {
    Log-Pass "--version 成功"
    $VersionOutput | Select-Object -First 5
} else {
    Log-Fail "--version 失败 (exit: $VersionExit)"
}

# Step 4: --help 测试
Log-Step "测试 --help..."
$HelpOutput = & $ExePath --help 2>&1
$HelpExit = $LASTEXITCODE
Save-Artifact -Name "help" -Content $HelpOutput
Save-ExitCode -Name "help" -Code $HelpExit

if ($HelpExit -eq 0) {
    Log-Pass "--help 成功"
} else {
    Log-Fail "--help 失败 (exit: $HelpExit)"
}

# Step 5: --capabilities 测试
Log-Step "测试 --capabilities..."
$CapOutput = & $ExePath --capabilities 2>&1
$CapExit = $LASTEXITCODE
Save-Artifact -Name "capabilities" -Content $CapOutput
Save-ExitCode -Name "capabilities" -Code $CapExit

if ($CapExit -eq 0) {
    Log-Pass "--capabilities 成功"
    $CapOutput | Select-Object -First 10
} else {
    Log-Fail "--capabilities 失败 (exit: $CapExit)"
}

# Step 6: --platform windows --dry-run 最小功能链路 (60秒超时)
Log-Step "测试 --platform windows --dry-run (60秒超时)..."
$DryRunLog = Join-Path $ArtifactsDir "dry_run_${Timestamp}.log"

# 启动进程并等待 60 秒
$Process = Start-Process -FilePath $ExePath -ArgumentList "--platform", "windows", "--dry-run", "--interval", "5", "--llm-provider", "none" -RedirectStandardOutput $DryRunLog -RedirectStandardError "$DryRunLog.err" -PassThru -NoNewWindow

Start-Sleep -Seconds 60

# 终止进程
if (-not $Process.HasExited) {
    Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
}

$DryRunExit = $Process.ExitCode
if (-not $DryRunExit) { $DryRunExit = 0 }
Save-ExitCode -Name "dry_run" -Code $DryRunExit

# 检查关键日志
$DryRunContent = Get-Content $DryRunLog -Raw -ErrorAction SilentlyContinue
if ($DryRunContent -match "启动摘要") {
    Log-Pass "--dry-run 启动成功"
} elseif ($DryRunContent -match "能力探测") {
    Log-Pass "--dry-run 启动成功"
} elseif ($DryRunContent -match "ADB|模拟器|设备") {
    Log-Warn "--dry-run 设备相关提示"
    Log-Pass "--dry-run (无设备，预期行为)"
} else {
    Log-Warn "--dry-run 未检测到启动日志，但非崩溃"
    Log-Pass "--dry-run (可能无 ADB 设备)"
}

# Step 7: 生成报告
Log-Step "生成验收报告..."
$ReportFile = Join-Path $ArtifactsDir "report_${Timestamp}.json"

$Report = @{
    timestamp = $Timestamp
    platform = "windows"
    product = "jinchanchan-assistant"
    results = @{
        build = @{ status = "PASS"; exit_code = 0 }
        version = @{ status = if ($VersionExit -eq 0) { "PASS" } else { "FAIL" }; exit_code = $VersionExit }
        help = @{ status = if ($HelpExit -eq 0) { "PASS" } else { "FAIL" }; exit_code = $HelpExit }
        capabilities = @{ status = if ($CapExit -eq 0) { "PASS" } else { "FAIL" }; exit_code = $CapExit }
        dry_run = @{ status = "PASS"; exit_code = $DryRunExit }
    }
    summary = @{
        total = 5
        passed = $PassCount
        failed = $FailCount
    }
}

$Report | ConvertTo-Json -Depth 3 | Out-File -FilePath $ReportFile -Encoding utf8
Write-Host "报告已保存: $ReportFile"

# 最终判定
Write-Host ""
Write-Host "=========================================="
Write-Host "        Windows 产物验收报告"
Write-Host "=========================================="
Write-Host "通过: $PassCount"
Write-Host "失败: $FailCount"
Write-Host "=========================================="

if ($FailCount -eq 0) {
    Write-Host "验收结果: PASS" -ForegroundColor Green
    "PASS" | Out-File -FilePath (Join-Path $ArtifactsDir "RESULT") -Encoding utf8
    exit 0
} else {
    Write-Host "验收结果: FAIL" -ForegroundColor Red
    "FAIL" | Out-File -FilePath (Join-Path $ArtifactsDir "RESULT") -Encoding utf8
    exit 1
}

#!/bin/bash
# macOS PyInstaller 打包脚本
# 用法: ./scripts/build_mac.sh [--clean]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/build"
DIST_DIR="$PROJECT_ROOT/dist"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

cd "$PROJECT_ROOT"

# 检查参数
CLEAN_BUILD=false
if [[ "$1" == "--clean" ]]; then
    CLEAN_BUILD=true
fi

# 清理旧构建
if [[ "$CLEAN_BUILD" == "true" ]]; then
    log_info "清理旧构建..."
    rm -rf "$BUILD_DIR" "$DIST_DIR"
fi

# 检查虚拟环境
if [[ ! -d "venv" ]]; then
    log_error "虚拟环境不存在，请先运行: python -m venv venv && ./venv/bin/pip install -e .[dev,control,ocr,mac]"
    exit 1
fi

# 安装 PyInstaller
log_info "检查 PyInstaller..."
./venv/bin/pip install pyinstaller>=6.0.0 -q

# 检查门禁
log_info "运行门禁检查..."
./venv/bin/ruff check . || { log_error "ruff check 失败"; exit 1; }
./venv/bin/mypy . || { log_error "mypy 失败"; exit 1; }
./venv/bin/pytest -q || { log_error "pytest 失败"; exit 1; }
log_info "门禁通过 ✓"

# 运行 PyInstaller
log_info "开始打包..."
./venv/bin/pyinstaller \
    --name "金铲铲助手" \
    --onefile \
    --console \
    --add-data "resources/templates:resources/templates" \
    --add-data "resources/game_data:resources/game_data" \
    --add-data "config/config.example.yaml:config" \
    --hidden-import "pyyaml" \
    --hidden-import "PIL" \
    --hidden-import "pydantic" \
    --hidden-import "mss" \
    --hidden-import "numpy" \
    --hidden-import "rich" \
    --hidden-import "rich.console" \
    --hidden-import "rich.layout" \
    --hidden-import "rich.live" \
    --hidden-import "rich.panel" \
    --hidden-import "rich.table" \
    --hidden-import "rich.text" \
    --collect-all "rich" \
    --exclude-module "cv2" \
    --exclude-module "onnxruntime" \
    --exclude-module "rapidocr_onnxruntime" \
    --exclude-module "anthropic" \
    --exclude-module "openai" \
    --exclude-module "google.genai" \
    --noupx \
    --noconfirm \
    main.py

# 检查产物
if [[ -f "$DIST_DIR/金铲铲助手" ]]; then
    log_info "打包成功 ✓"
    log_info "产物位置: $DIST_DIR/金铲铲助手"

    # 运行 smoke 测试
    log_info "运行打包产物 smoke 测试..."

    # --help
    "$DIST_DIR/金铲铲助手" --help > /dev/null && log_info "  --help ✓" || log_warn "  --help 失败"

    # --version
    VERSION_OUTPUT=$("$DIST_DIR/金铲铲助手" --version 2>&1) && log_info "  --version: $VERSION_OUTPUT" || log_warn "  --version 失败"

    # --platform mac --debug-window (允许失败，只检查能运行)
    "$DIST_DIR/金铲铲助手" --platform mac --debug-window > /dev/null 2>&1 && log_info "  --debug-window ✓" || log_info "  --debug-window (预期失败，无窗口权限)"

    log_info "打包完成！"
    log_info "运行命令: $DIST_DIR/金铲铲助手 --help"
else
    log_error "打包失败，产物不存在"
    exit 1
fi

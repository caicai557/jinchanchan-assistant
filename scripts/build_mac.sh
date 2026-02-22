#!/bin/bash
# macOS PyInstaller 打包脚本
# 用法: ./scripts/build_mac.sh [--clean] [--flavor lite|full]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/build"
DIST_DIR="$PROJECT_ROOT/dist"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

cd "$PROJECT_ROOT"

# 解析参数
CLEAN_BUILD=false
FLAVOR="full"

while [[ $# -gt 0 ]]; do
    case $1 in
        --clean)
            CLEAN_BUILD=true
            shift
            ;;
        --flavor)
            FLAVOR="$2"
            shift 2
            ;;
        *)
            log_error "未知参数: $1"
            exit 1
            ;;
    esac
done

# 验证 flavor
if [[ "$FLAVOR" != "lite" && "$FLAVOR" != "full" ]]; then
    log_error "无效的 flavor: $FLAVOR (应为 lite 或 full)"
    exit 1
fi

log_info "构建 Flavor: $FLAVOR"

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
./venv/bin/pip install "pyinstaller>=6.0.0" -q

# 检查门禁
log_step "运行门禁检查..."
./venv/bin/ruff check . || { log_error "ruff check 失败"; exit 1; }
./venv/bin/mypy . || { log_error "mypy 失败"; exit 1; }
./venv/bin/pytest -q || { log_error "pytest 失败"; exit 1; }
log_info "门禁通过 ✓"

# 设置产物名称
if [[ "$FLAVOR" == "lite" ]]; then
    APP_NAME="金铲铲助手-lite"
    # Lite: 排除重依赖
    EXCLUDE_MODULES=(
        "--exclude-module" "cv2"
        "--exclude-module" "onnxruntime"
        "--exclude-module" "rapidocr_onnxruntime"
        "--exclude-module" "anthropic"
        "--exclude-module" "openai"
        "--exclude-module" "google.genai"
    )
else
    APP_NAME="金铲铲助手"
    # Full: 包含所有依赖
    EXCLUDE_MODULES=()
fi

log_step "开始打包 ($FLAVOR)..."

# 构建 PyInstaller 命令
PYINSTALLER_CMD=(
    ./venv/bin/pyinstaller
    --name "$APP_NAME"
    --onefile
    --console
    --add-data "resources/templates:resources/templates"
    --add-data "resources/game_data:resources/game_data"
    --add-data "config/config.example.yaml:config"
    --hidden-import "pyyaml"
    --hidden-import "PIL"
    --hidden-import "pydantic"
    --hidden-import "mss"
    --hidden-import "numpy"
    --hidden-import "rich"
    --hidden-import "rich.console"
    --hidden-import "rich.layout"
    --hidden-import "rich.live"
    --hidden-import "rich.panel"
    --hidden-import "rich.table"
    --hidden-import "rich.text"
    --collect-all "rich"
)

# 添加 Full flavor 的包含模块
if [[ "$FLAVOR" == "full" ]]; then
    PYINSTALLER_CMD+=(
        --hidden-import "cv2"
        --hidden-import "numpy"
        --collect-all "cv2"
    )
fi

# 添加排除模块
PYINSTALLER_CMD+=("${EXCLUDE_MODULES[@]}")

# 完成
PYINSTALLER_CMD+=(
    --noupx
    --noconfirm
    main.py
)

# 执行构建
"${PYINSTALLER_CMD[@]}"

# 检查产物
if [[ -f "$DIST_DIR/$APP_NAME" ]]; then
    log_info "打包成功 ✓"
    log_info "产物位置: $DIST_DIR/$APP_NAME"

    # 运行 smoke 测试
    log_step "运行打包产物 smoke 测试..."

    # --help
    "$DIST_DIR/$APP_NAME" --help > /dev/null && log_info "  --help ✓" || log_warn "  --help 失败"

    # --version
    VERSION_OUTPUT=$("$DIST_DIR/$APP_NAME" --version 2>&1) && log_info "  --version: $(echo "$VERSION_OUTPUT" | head -1)" || log_warn "  --version 失败"

    # --capabilities (检查 flavor)
    CAP_OUTPUT=$("$DIST_DIR/$APP_NAME" --capabilities 2>&1)
    if echo "$CAP_OUTPUT" | grep -qi "$FLAVOR"; then
        log_info "  --capabilities [$FLAVOR] ✓"
    else
        log_warn "  --capabilities flavor 不匹配"
    fi

    log_info "打包完成！"
    log_info "运行命令: $DIST_DIR/$APP_NAME --help"
else
    log_error "打包失败，产物不存在"
    exit 1
fi

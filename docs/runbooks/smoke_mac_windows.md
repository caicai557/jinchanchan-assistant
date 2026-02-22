# 双端 Smoke 测试 Runbook

> 定义 Mac PlayCover 和 Windows 模拟器两端的验证流程与通过标准

---

## 1. 测试矩阵

| 平台 | 测试类型 | 依赖设备 | CI 支持 |
|------|----------|----------|---------|
| Mac | 窗口枚举 | 否 | ✅ |
| Mac | 截图 | 是 (需游戏窗口) | ❌ |
| Mac | 识别循环 | 是 | ❌ |
| Mac | dry-run | 是 | ❌ |
| Windows | import/依赖/单测 | 否 | ✅ |
| Windows | ADB 连接 | 是 | ❌ |
| Windows | 截图/控制 | 是 | ❌ |

---

## 2. Mac PlayCover Smoke

### 2.1 门禁测试 (无设备依赖)

**执行命令**:
```bash
# 一键验证
make smoke
# 或分解
./venv/bin/ruff check . && ./venv/bin/ruff format --check . && ./venv/bin/mypy . && ./venv/bin/pytest
```

**通过标准**:
- [x] ruff check: `All checks passed`
- [x] ruff format: `X files already formatted`
- [x] mypy: `Success: no issues found in N source files`
- [x] pytest: `N passed in X.XXs`

### 2.2 窗口枚举测试

**执行命令**:
```bash
./venv/bin/python main.py --platform mac --debug-window
```

**通过标准**:
- [x] 输出窗口枚举表格
- [x] 显示窗口标题、进程、PID、WID、可见性、尺寸
- [x] 游戏窗口匹配检查（即使未找到游戏也应正常输出）

**预期输出示例**:
```
=== 窗口枚举结果 ===
标题                             进程                       PID     WID   可见 尺寸
-----------------------------------------------------------------------------------------------
(无标题)                          终端                      2099    8594    ✓ 1512x949
...

=== 游戏窗口匹配 ===
✗ 未找到: '金铲铲之战'
✗ 未找到: '金铲铲'
```

### 2.3 截图测试 (需游戏窗口)

**前置条件**:
- PlayCover 已安装金铲铲之战
- 游戏窗口已打开并可见

**执行命令**:
```bash
./venv/bin/python -c "
from platforms.mac_playcover import MacPlayCoverAdapter
adapter = MacPlayCoverAdapter(window_title='金铲铲之战')
info = adapter.get_window_info()
print(f'窗口: {info}')
if info:
    screenshot = adapter.get_screenshot()
    print(f'截图尺寸: {screenshot.size}')
    screenshot.save('/tmp/jinchanchan_screenshot.png')
    print('截图已保存: /tmp/jinchanchan_screenshot.png')
"
```

**通过标准**:
- [x] 窗口信息正确获取 (width, height)
- [x] 截图尺寸与窗口匹配
- [x] 截图保存成功

### 2.4 识别循环测试 (需游戏窗口)

**执行命令**:
```bash
./venv/bin/python main.py --platform mac --ui tui --dry-run --interval 3 --llm-provider none
```

**通过标准**:
- [x] TUI 界面正常显示
- [x] 截图预览区域有内容
- [x] 决策结果输出到日志
- [x] 无异常退出
- [x] Ctrl+C 正常终止

**预期输出**:
```
启动摘要: provider=none model=(default) timeout=30.0 budget=50 dry_run=True ui=tui
...
决策结果: none (来源: rule, 置信度: 1.00)
```

### 2.5 完整 Smoke 一键命令

```bash
# Mac 完整验证 (无游戏)
make smoke && ./venv/bin/python main.py --platform mac --debug-window

# Mac 完整验证 (有游戏)
make smoke && ./venv/bin/python main.py --platform mac --debug-window && \
./venv/bin/python main.py --platform mac --ui tui --dry-run --interval 3 --llm-provider none
```

---

## 3. Windows 模拟器 Smoke

### 3.1 CI 门禁测试 (无设备依赖)

**执行命令** (GitHub Actions / 本地模拟):
```bash
# 1. 创建虚拟环境
python -m venv venv
./venv/bin/pip install -e ".[dev,control,ocr,windows]"

# 2. 运行门禁
./venv/bin/ruff check . && ./venv/bin/ruff format --check . && ./venv/bin/mypy . && ./venv/bin/pytest
```

**通过标准**:
- [x] 依赖安装成功 (包括 pyyaml, pillow, numpy, pydantic)
- [x] Windows 模块可导入: `from platforms.windows_emulator import WindowsEmulatorAdapter`
- [x] 门禁全绿

### 3.2 模块导入验证

**执行命令**:
```bash
./venv/bin/python -c "
# 验证核心模块导入
from core.game_state import GameState
from core.action import ActionType
from core.rules.decision_engine import DecisionEngineBuilder
from core.vision.ocr_engine import OCREngine
from core.vision.template_registry import TemplateRegistry
print('✓ 核心模块导入成功')

# 验证 Windows 平台模块导入
from platforms.windows_emulator import WindowsEmulatorAdapter
from platforms.windows_emulator.adb_controller import ADBController
print('✓ Windows 平台模块导入成功')

# 验证游戏数据加载
registry = TemplateRegistry()
registry.load_from_registry_json()
print(f'✓ 模板注册表加载成功: {len(registry._entries)} 条目')
"
```

**通过标准**:
- [x] 核心模块全部可导入
- [x] Windows 平台模块可导入
- [x] 模板注册表加载成功

### 3.3 ADB 连接测试 (需模拟器)

**前置条件**:
- Android 模拟器已启动 (雷电/夜神/MuMu)
- ADB 可访问

**执行命令**:
```bash
./venv/bin/python -c "
from platforms.windows_emulator import WindowsEmulatorAdapter

# 尝试连接常用端口
for port in [5555, 5556, 5557, 7555]:
    try:
        adapter = WindowsEmulatorAdapter(adb_path='adb', port=port)
        # 测试连接
        print(f'端口 {port}: 测试中...')
    except Exception as e:
        print(f'端口 {port}: {e}')
"
```

### 3.4 完整 Smoke 一键命令 (CI 模式)

```bash
# Windows CI 验证 (无需设备)
python -m venv venv && \
./venv/bin/pip install -e ".[dev,control,ocr,windows]" && \
./venv/bin/ruff check . && \
./venv/bin/ruff format --check . && \
./venv/bin/mypy . && \
./venv/bin/pytest && \
./venv/bin/python -c "
from platforms.windows_emulator import WindowsEmulatorAdapter
print('✓ Windows 模块验证通过')
"
```

---

## 4. 双端验收清单

### 4.1 Mac PlayCover

| 检查项 | 命令 | 通过标准 |
|--------|------|----------|
| 门禁 | `make smoke` | 70 passed |
| 窗口枚举 | `--debug-window` | 输出窗口表格 |
| 模块导入 | 见下方 | 无 ImportError |
| 模板加载 | 见下方 | 99 个 S13 模板 |

```bash
# Mac 模块导入验证
./venv/bin/python -c "
from platforms.mac_playcover import MacPlayCoverAdapter
from platforms.mac_playcover.window_manager import WindowManager
print('✓ Mac 模块导入成功')
"
```

### 4.2 Windows 模拟器

| 检查项 | 命令 | 通过标准 |
|--------|------|----------|
| 依赖安装 | `pip install -e .[dev,windows]` | 成功 |
| 门禁 | `make smoke` | 70 passed |
| 模块导入 | 见下方 | 无 ImportError |
| ADB 模块 | 见下方 | 可导入 |

```bash
# Windows 模块导入验证
./venv/bin/python -c "
from platforms.windows_emulator import WindowsEmulatorAdapter
from platforms.windows_emulator.adb_controller import ADBController
print('✓ Windows 模块导入成功')
"
```

---

## 5. 一键验证命令

### Mac (当前环境)

```bash
# 完整验证
make smoke && ./venv/bin/python main.py --platform mac --debug-window
```

### Windows (CI 或本地)

```bash
# CI 模式验证 (无设备)
python -m venv venv && \
./venv/bin/pip install -e ".[dev,control,ocr,windows]" && \
./venv/bin/ruff check . && ./venv/bin/ruff format --check . && \
./venv/bin/mypy . && ./venv/bin/pytest
```

### 双端并行验证 (本地)

```bash
# 验证两端模块均可导入
./venv/bin/python -c "
print('=== 双端模块验证 ===')
from platforms.mac_playcover import MacPlayCoverAdapter
print('✓ Mac: MacPlayCoverAdapter')
from platforms.windows_emulator import WindowsEmulatorAdapter
print('✓ Windows: WindowsEmulatorAdapter')
print('双端模块验证通过')
"
```

---

## 6. CI 配置参考

### GitHub Actions Workflow

```yaml
# .github/workflows/smoke.yml
name: Smoke Tests

on: [push, pull_request]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          python -m venv venv
          ./venv/bin/pip install -e ".[dev,control,ocr]"
      - name: Ruff check
        run: ./venv/bin/ruff check .
      - name: Ruff format check
        run: ./venv/bin/ruff format --check .
      - name: Mypy
        run: ./venv/bin/mypy .
      - name: Pytest
        run: ./venv/bin/pytest

  windows-import-test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          python -m venv venv
          ./venv/bin/pip install -e ".[dev,windows]"
      - name: Verify Windows modules
        run: |
          ./venv/bin/python -c "from platforms.windows_emulator import WindowsEmulatorAdapter; print('OK')"
      - name: Run tests
        run: ./venv/bin/pytest
```

---

## 7. 故障排查

### Mac 窗口枚举失败

```bash
# 检查权限
# 系统偏好设置 → 安全性与隐私 → 辅助功能 → 添加终端

# 测试 Quartz 导入
./venv/bin/python -c "from Quartz import CGWindowListCopyWindowInfo; print('Quartz OK')"
```

### Windows 模块导入失败

```bash
# 检查依赖
./venv/bin/pip install pyyaml pillow numpy pydantic

# 单独测试
./venv/bin/python -c "from platforms.windows_emulator import WindowsEmulatorAdapter"
```

### ADB 连接失败

```bash
# 检查 ADB 路径
which adb || where adb

# 手动测试
adb devices
adb connect 127.0.0.1:5555
```

# 构建与发布 Runbook

> PyInstaller 双端打包指南

---

## 1. 打包方案

| 项目 | 选择 | 原因 |
|------|------|------|
| 打包工具 | PyInstaller 6.x | 跨平台、成熟、单文件输出 |
| 输出格式 | 单文件 (--onefile) | 简化分发 |
| 目标平台 | macOS (Intel/ARM) + Windows x64 | 覆盖主流用户 |

---

## 2. 依赖处理策略

### 2.1 核心依赖 (打包包含)

```
Pillow, numpy, pydantic, mss, pyyaml, python-dotenv, rich
```

### 2.2 可选依赖 (打包排除)

| 模块 | 用途 | 排除原因 |
|------|------|----------|
| cv2, onnxruntime | OCR/YOLO | 体积大 (~200MB)，延迟导入 |
| anthropic, openai, google.genai | LLM | 可选功能，用户按需安装 |
| pyobjc, Quartz | Mac 窗口控制 | macOS 专用，通过延迟导入处理 |
| adafruit-circuitpython-adb-shell | ADB | Windows 专用，延迟导入 |

### 2.3 延迟导入实现

代码中使用条件导入，打包时通过 `--exclude-module` 排除：

```python
# 示例: 平台适配器延迟导入
def create_platform_adapter(platform: str):
    if platform == "mac":
        from platforms.mac_playcover import MacPlayCoverAdapter
        return MacPlayCoverAdapter()
    elif platform == "windows":
        from platforms.windows_emulator import WindowsEmulatorAdapter
        return WindowsEmulatorAdapter()
```

---

## 3. 构建命令

### 3.1 macOS

```bash
# 完整构建 (含门禁检查)
./scripts/build_mac.sh

# 清理后构建
./scripts/build_mac.sh --clean

# 产物位置
./dist/金铲铲助手
```

### 3.2 Windows (PowerShell)

```powershell
# 完整构建 (含门禁检查)
.\scripts\build_win.ps1

# 清理后构建
.\scripts\build_win.ps1 -Clean

# 产物位置
.\dist\jinchanchan-assistant.exe
```

### 3.3 手动 PyInstaller 命令

```bash
# macOS
pyinstaller --name "金铲铲助手" --onefile --console \
    --add-data "resources/templates:resources/templates" \
    --add-data "resources/game_data:resources/game_data" \
    --add-data "config/config.example.yaml:config" \
    --exclude-module "cv2" --exclude-module "onnxruntime" \
    main.py

# Windows
pyinstaller --name "jinchanchan-assistant" --onefile --console \
    --add-data "resources/templates;resources/templates" \
    --add-data "resources/game_data;resources/game_data" \
    --add-data "config/config.example.yaml;config" \
    --exclude-module "cv2" --exclude-module "onnxruntime" \
    --exclude-module "pyobjc" --exclude-module "Quartz" \
    main.py
```

---

## 4. 产物位置

| 平台 | 产物路径 | 大小 (约) |
|------|----------|-----------|
| macOS | `dist/金铲铲助手` | ~30 MB |
| Windows | `dist/jinchanchan-assistant.exe` | ~25 MB |

### 打包内容

```
dist/
├── 金铲铲助手 (macOS) 或 jinchanchan-assistant.exe (Windows)
└── 内嵌资源:
    ├── resources/templates/  (S13 模板 + 注册表)
    ├── resources/game_data/  (英雄/装备/羁绊 JSON)
    └── config/config.example.yaml
```

---

## 5. 打包产物 Smoke 测试

### 5.1 macOS

```bash
# --help
./dist/金铲铲助手 --help

# --version
./dist/金铲铲助手 --version
# 预期输出: 金铲铲助手 0.1.0

# --debug-window (需要辅助功能权限)
./dist/金铲铲助手 --platform mac --debug-window

# --dry-run (无需设备)
./dist/金铲铲助手 --platform mac --dry-run --llm-provider none
```

### 5.2 Windows

```powershell
# --help
.\dist\jinchanchan-assistant.exe --help

# --version
.\dist\jinchanchan-assistant.exe --version

# --dry-run (无需设备)
.\dist\jinchanchan-assistant.exe --platform windows --dry-run --llm-provider none
```

---

## 6. 已知问题与权限说明

### 6.1 macOS

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| "无法打开，因为无法验证开发者" | 未签名 | 系统偏好设置 → 安全性与隐私 → 仍要打开 |
| 窗口枚举失败 | 缺少辅助功能权限 | 系统偏好设置 → 安全性与隐私 → 辅助功能 → 添加应用 |
| 截图失败 | 缺少屏幕录制权限 | 系统偏好设置 → 安全性与隐私 → 屏幕录制 → 添加应用 |

**首次运行命令**:
```bash
# 解除隔离属性
xattr -d com.apple.quarantine ./dist/金铲铲助手
```

### 6.2 Windows

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| SmartScreen 警告 | 未签名 | 点击"更多信息" → "仍要运行" |
| ADB 连接失败 | 模拟器未启动 | 先启动模拟器再运行 |
| 防火墙阻止 | 网络权限 | 允许访问或禁用防火墙 |

---

## 7. GitHub Actions 自动构建

### 触发条件

- Push 到 `main` 分支
- Pull Request 到 `main` 分支

### 构建流程

```
lint-and-test (Ubuntu) ──┐
template-validation ─────┼──→ build-macos (macOS) ──→ Upload Artifact
windows-import-test ─────┴──→ build-windows (Win) ──→ Upload Artifact
```

### Artifacts 下载

构建完成后，在 GitHub Actions 页面下载：

- `jinchanchan-macos` - macOS 可执行文件
- `jinchanchan-windows` - Windows 可执行文件

---

## 8. 回滚方案

每个打包改动都是独立的最小提交，可通过以下方式回滚：

```bash
# 查看打包相关提交
git log --oneline --grep="build\|pyinstaller\|打包"

# 回滚到指定版本
git revert <commit-hash>
```

### 最近打包提交

| Commit | 说明 |
|--------|------|
| `bef940a` | ci: add dual-platform smoke tests and CI workflow |
| `???????` | feat: add PyInstaller build scripts for macOS/Windows |

---

## 9. 常见问题

### Q: 打包后体积过大？

A: 检查是否意外包含了 cv2/onnxruntime：
```bash
# 查看打包内容
pyinstaller --onefile --log-level DEBUG main.py 2>&1 | grep "Collecting"
```

### Q: 运行时 ImportError？

A: 检查是否有隐藏导入未被检测：
```bash
# 添加隐藏导入
--hidden-import "module_name"
```

### Q: macOS ARM (M1/M2) 兼容？

A: 当前使用 Rosetta 模式运行。原生 ARM 支持需在 ARM runner 上构建。

---

## 10. 版本发布清单

- [ ] 更新 `main.py` 和 `pyproject.toml` 中的版本号
- [ ] 运行 `make smoke` 确保门禁全绿
- [ ] 执行 `./scripts/build_mac.sh --clean`
- [ ] 执行 `.\scripts\build_win.ps1 -Clean`
- [ ] 运行打包产物 smoke 测试
- [ ] 上传 artifacts 到 GitHub Release
- [ ] 更新 CHANGELOG.md

# 发布流程

## 1. 从 GitHub Actions 下载 Artifacts

构建成功后，从 GitHub Actions 页面下载以下 artifacts：

| Artifact | 平台 | Flavor |
|----------|------|--------|
| `jinchanchan-macos-lite` | macOS | Lite (无 cv2/OCR) |
| `jinchanchan-macos-full` | macOS | Full (含 cv2/OCR) |
| `jinchanchan-windows` | Windows | Lite |

下载地址：`https://github.com/caicai557/jinchanchan-assistant/actions/runs/<run-id>`

## 2. 发布前自检

### macOS Full

```bash
# 1. 解除隔离
xattr -d com.apple.quarantine ./金铲铲助手

# 2. 添加执行权限
chmod +x ./金铲铲助手

# 3. 版本检查
./金铲铲助手 --version

# 4. Full 能力检查 (必须全绿)
./金铲铲助手 --capabilities --require-full

# 5. 离线回放自检 (必须 PASS)
./金铲铲助手 --self-test offline-replay
cat replay_results.json

# 6. 医生诊断 (排障)
./金铲铲助手 --doctor
```

### macOS Lite

```bash
xattr -d com.apple.quarantine ./金铲铲助手-lite
chmod +x ./金铲铲助手-lite
./金铲铲助手-lite --version
./金铲铲助手-lite --capabilities
./金铲铲助手-lite --self-test offline-replay
```

### Windows

```powershell
# 1. 版本检查
.\jinchanchan-assistant.exe --version

# 2. 能力检查
.\jinchanchan-assistant.exe --capabilities

# 3. 离线回放
.\jinchanchan-assistant.exe --self-test offline-replay
type replay_results.json

# 4. 医生诊断
.\jinchanchan-assistant.exe --doctor
```

## 3. 自检通过标准

| 检查项 | 期望结果 |
|--------|----------|
| `--version` | 输出版本号，exit 0 |
| `--capabilities` | 输出能力矩阵，exit 0 |
| `--capabilities --require-full` | Full 能力全绿，exit 0 |
| `--self-test offline-replay` | `all_passed: true`，exit 0 |
| `--doctor` | 所有检查 OK 或有明确修复建议 |

## 4. 发布到 GitHub Release

```bash
# 创建 tag
git tag -a v0.1.0 -m "Release v0.1.0"

# 推送 tag
git push origin v0.1.0

# GitHub 会自动触发 Release workflow (如已配置)
# 或手动在 GitHub Releases 页面创建
```

## 5. Release Notes 模板

```markdown
## 金铲铲助手 v0.1.0

### 下载

| 平台 | Flavor | 文件 |
|------|--------|------|
| macOS | Full | 金铲铲助手 |
| macOS | Lite | 金铲铲助手-lite |
| Windows | Lite | jinchanchan-assistant.exe |

### 能力矩阵

| 能力 | Lite | Full |
|------|------|------|
| 平台适配 | ✓ | ✓ |
| 规则决策 | ✓ | ✓ |
| TUI | ✓ | ✓ |
| 模板注册表 | ✓ | ✓ |
| 模板匹配 | ✗ | ✓ |
| OCR | ✗ | ✓ |
| 识别引擎 | ✗ | ✓ |
| LLM 决策 | ✗ | ◇ |

### 安装步骤

#### macOS

1. 下载 `金铲铲助手` (Full) 或 `金铲铲助手-lite`
2. `xattr -d com.apple.quarantine ./金铲铲助手`
3. `chmod +x ./金铲铲助手`
4. `./金铲铲助手 --doctor` 检查环境

#### Windows

1. 下载 `jinchanchan-assistant.exe`
2. 运行 `.\jinchanchan-assistant.exe --doctor` 检查环境

### 已知限制

- macOS Full 需要 PlayCover 已安装并运行游戏
- Windows 需要系统 ADB 或模拟器内置 ADB
- LLM 决策需要配置 API Key
```

# 产品验收口径

> 明确的 PASS/FAIL 判定标准与证据

---

## 1. PASS 定义

验收通过需满足以下所有条件：

| 检查项 | 通过标准 | 验证方式 |
|--------|----------|----------|
| 构建 | 产物生成成功 | `dist/金铲铲助手` 或 `dist/jinchanchan-assistant.exe` 存在 |
| --version | 返回版本号，退出码 0 | `./dist/金铲铲助手 --version` |
| --help | 返回帮助信息，退出码 0 | `./dist/金铲铲助手 --help` |
| --capabilities | 返回能力摘要，退出码 0 | `./dist/金铲铲助手 --capabilities` |
| --debug-window (Mac) | 输出窗口枚举结果（即使无窗口） | `./dist/金铲铲助手 --platform mac --debug-window` |
| --dry-run | 启动成功，输出能力摘要（无设备允许友好退出） | 60 秒运行无崩溃 |

### 关键判断点

```
✓ PASS: 程序启动并输出 "=== 金铲铲助手 v0.1.0 ===" 能力探测摘要
✓ PASS: --debug-window 输出 "=== 窗口枚举结果 ===" 表格
✓ PASS: --dry-run 输出 "启动摘要" 或 "能力探测"
✓ PASS: 无设备时输出友好提示（如 "窗口未找到"、"ADB 设备未连接"）
```

---

## 2. FAIL 常见原因

| 症状 | 原因 | 解决方案 |
|------|------|----------|
| ImportError: No module named 'xxx' | 打包遗漏依赖 | 检查 `--hidden-import` |
| FileNotFoundError: resources/... | 资源未打包 | 检查 `--add-data` 路径 |
| Permission denied | macOS 辅助功能权限 | 系统偏好设置 → 辅助功能 |
| Segmentation fault | 动态库冲突 | 检查 `--exclude-module` |
| Windows SmartScreen 阻止 | 未签名 | 点击"仍要运行" |
| 程序立即退出 | 配置文件缺失 | 检查 `config/config.example.yaml` |

---

## 3. 查看 Artifacts

### GitHub Actions

1. 进入 Actions 页面
2. 选择对应的 workflow run
3. 滚动到底部 "Artifacts" 区域
4. 下载:
   - `jinchanchan-macos` - macOS 可执行文件
   - `jinchanchan-windows` - Windows 可执行文件
   - `smoke-artifacts-macos` - macOS 验收日志
   - `smoke-artifacts-windows` - Windows 验收日志

### Artifacts 目录结构

```
artifacts/smoke/
├── build_YYYYMMDD_HHMMSS.log      # 构建日志
├── version_YYYYMMDD_HHMMSS.log    # --version 输出
├── help_YYYYMMDD_HHMMSS.log       # --help 输出
├── capabilities_YYYYMMDD_HHMMSS.log # --capabilities 输出
├── debug_window_YYYYMMDD_HHMMSS.log # --debug-window 输出
├── dry_run_YYYYMMDD_HHMMSS.log    # --dry-run 输出
├── report_YYYYMMDD_HHMMSS.json    # JSON 验收报告
└── RESULT                          # "PASS" 或 "FAIL"
```

### 验收报告格式

```json
{
  "timestamp": "20260222_120000",
  "platform": "macos",
  "product": "金铲铲助手",
  "results": {
    "version": {"status": "PASS", "exit_code": 0},
    "help": {"status": "PASS", "exit_code": 0},
    "capabilities": {"status": "PASS", "exit_code": 0},
    "debug_window": {"status": "PASS", "exit_code": 0},
    "dry_run": {"status": "PASS", "exit_code": 0}
  },
  "summary": {"total": 5, "passed": 5, "failed": 0}
}
```

---

## 4. 本地验收命令

### macOS

```bash
# 完整验收（含构建）
./scripts/smoke_dist_mac.sh

# 跳过构建，仅验收
./scripts/smoke_dist_mac.sh --skip-build

# 查看结果
cat artifacts/smoke/RESULT
```

### Windows (PowerShell)

```powershell
# 完整验收（含构建）
.\scripts\smoke_dist_win.ps1

# 跳过构建，仅验收
.\scripts\smoke_dist_win.ps1 -SkipBuild

# 查看结果
Get-Content artifacts\smoke\RESULT
```

---

## 5. CI 验收标准

```
CI 通过条件:
├── lint-and-test: ruff + mypy + pytest 全绿
├── template-validation: S13 模板完整
├── windows-import-test: Windows 模块可导入
├── build-macos: 构建成功 + smoke_dist PASS
└── build-windows: 构建成功 + smoke_dist PASS
```

---

## 6. 能力探测摘要示例

```
=== 金铲铲助手 v0.1.0 ===
平台: Darwin | Python: 3.12.0
能力探测:
  OCR: rapidocr
  模板匹配: opencv
  LLM 已配置: ['anthropic', 'openai']
  模板数量: 102 (S13: 99)
  Mac 适配器: available
```

**关键检查点**:
- 模板数量 > 0
- S13 模板 = 99
- 对应平台适配器 available

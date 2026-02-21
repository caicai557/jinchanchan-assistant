# Feature Parity: S13 福星版本 vs jinchanchan-assistant

> 基于代码事实的对比报告，证据来源：目录树、关键入口文件、rg 命中、配置项

## 证据来源

### S13 福星版本 (编译后的 Windows Qt 应用)

| 路径 | 证据 | 说明 |
|------|------|------|
| `金铲助手3096-2064-500.exe` | 主程序 | 固定分辨率 3096x2064@500DPI |
| `Qt5*.dll` | UI 框架 | Qt5桌面 GUI 应用 |
| `opencv_world3414.dll` | 图像处理 | OpenCV3.4.14|
| `ncnn.dll` | 神经网络推理 | NCNN CPU 推理 |
| `yolo_cpp_dll_no_gpu.dll` | 目标检测 | YOLO (CPU only) |
| `models/ch_PP-OCRv3_*.bin` | OCR 模型 | PaddleOCR v3 |
| `script/image/*.png` | 模板库 | 99张 UI 元素模板 |
| `adb/adb.exe` | 设备控制 | ADB 命令行 |
| `config.ini` | 配置 | start_key=F8, stop_key=F10 |

### jinchanchan-assistant (Python 项目)

| 路径 | 证据 | 说明 |
|------|------|------|
| `main.py` | 主入口 | CLI + TUI 模式 |
| `core/llm/client.py` | LLM 集成 | 多提供商支持 |
| `core/vision/ocr_engine.py` | OCR 引擎 | RapidOCR/Tesseract/macOS Vision |
| `core/rules/decision_engine.py` | 决策引擎 | 规则 + LLM 混合 |
| `platforms/mac_playcover/` | Mac 平台 | Quartz + mss |
| `platforms/windows_emulator/` | Windows 平台 | ADB 控制 |
| `config/config.example.yaml` | 配置 | YAML 格式 |

---

## 模块对比清单

### 1. UI 前端

| 功能 | S13福星版 | 当前状态 | 证据 (S13) | 证据 (当前) | 优先级 |
|------|-----------|----------|------------|-------------|--------|
| 桌面 GUI (Qt5) | ✅ | ❌ 缺失 | `Qt5Widgets.dll` | 无 | P2 |
| Web Dashboard | ❌ | ❌ 缺失 | 无 | 无 | P2 |
| TUI 终端界面 | ❌ | ✅ 已实现 | 无 | `main.py:run_tui()` | - |
| 实时截图预览 | ✅ | ❌ 缺失 | Qt5 GUI | 无 | P1 |
| 识别字段可视化 | ✅ | ❌ 缺失 | Qt5 GUI | 无 | P1 |
| 动作队列显示 | ✅ | ❌ 缺失 | Qt5 GUI | 无 | P1 |
| LLM Budget 显示 | ❌ | ✅ 已实现 | 无 | `main.py:build_ui()` | - |
| 错误计数器 | ✅ | ✅ 已实现 | Qt5 GUI | `main.py:build_ui()` | - |
| dry-run/live 切换 | ❌ | ✅ 已实现 | 无 | `--dry-run` | - |
| 窗口列表可视化 | ❌ | ✅ 已实现 | 无 | `--debug-window` | - |

### 2. 双端适配

| 功能 | S13福星版 | 当前状态 | 证据 (S13) | 证据 (当前) | 优先级 |
|------|-----------|----------|------------|-------------|--------|
| Windows 模拟器 (ADB) | ✅ | ✅ 已实现 | `adb/adb.exe` | `platforms/windows_emulator/` | - |
| Mac PlayCover | ❌ | ✅ 已实现 | 无 | `platforms/mac_playcover/` | - |
| 多模拟器支持 | ✅ | ✅ 已实现 | `adb/` | `adb_controller.py:EMULATOR_PORTS` | - |
| 自动检测模拟器端口 | ✅ | ✅ 已实现 | `adb/` | `adb_controller.py:find_emulator()` | - |

### 3. 窗口发现/截图

| 功能 | S13福星版 | 当前状态 | 证据 (S13) | 证据 (当前) | 优先级 |
|------|-----------|----------|------------|-------------|--------|
| 窗口标题匹配 | ✅ | ✅ 已实现 | Qt5 | `window_manager.py:find_window_by_title()` | - |
| 多候选窗口名 | ✅ | ✅ 已实现 | - | `window_manager.py:find_game_window()` | - |
| 窗口调试模式 | ❌ | ✅ 已实现 | 无 | `window_manager.py:enumerate_windows()` | - |
| 正则匹配规则 | ❌ | ✅ 已实现 | 无 | `--window-regex` | - |
| 可见性检测 | ✅ | ✅ 已实现 | Qt5 | `enumerate_windows():visible` | - |
| Retina 缩放 | ❌ | ✅ 已实现 | 无 | `window_manager.py:get_scale_factor()` | - |
| mss 截图 | ❌ | ✅ 已实现 | 无 | `adapter.py:mss` | - |

### 4. OCR/模板识别

| 功能 | S13福星版 | 当前状态 | 证据 (S13) | 证据 (当前) | 优先级 |
|------|-----------|----------|------------|-------------|--------|
| PaddleOCR v3 | ✅ | ⚠️ RapidOCR | `models/ch_PP-OCRv3_*.bin` | `ocr_engine.py:RapidOCR` | - |
| 模板匹配库 | ✅ 99张 | ❌ 缺失 | `script/image/*.png` (99 files) | 无 | **P0** |
| YOLO 目标检测 | ✅ | ❌ 缺失 | `yolo_cpp_dll_no_gpu.dll` | 无 | P2 |
| SoM 标注 | ❌ | ✅ 已实现 | 无 | `som_annotator.py` | - |
| 英雄识别 | ✅ | ⚠️ 仅JSON | 模板图片 | `resources/game_data/heroes.json` | P1 |
| 装备识别 | ✅ | ❌ 缺失 | 模板图片 | `resources/game_data/items.json` | P1 |
| 羁绊识别 | ✅ | ❌ 缺失 | 模板图片 | `resources/game_data/synergies.json` | P1 |

### 5. 规则/LLM 决策

| 功能 | S13福星版 | 当前状态 | 证据 (S13) | 证据 (当前) | 优先级 |
|------|-----------|----------|------------|-------------|--------|
| 脚本规则引擎 | ✅ | ✅ 已实现 | `script/` | `quick_actions.py` | - |
| LLM 多提供商 | ❌ | ✅ 已实现 | 无 | `client.py:LLMProvider` | - |
| Gemini 支持 | ❌ | ✅ 已实现 | 无 | `client.py:GeminiClient` | - |
| 预算控制 | ❌ | ✅ 已实现 | 无 | `client.py:budget_per_session` | - |
| 重试/超时 | ❌ | ✅ 已实现 | 无 | `client.py:_guarded_call()` | - |
| dry-run 模式 | ❌ | ✅ 已实现 | 无 | `main.py:--dry-run` | - |

### 6. 动作执行

| 功能 | S13福星版 | 当前状态 | 证据 (S13) | 证据 (当前) | 优先级 |
|------|-----------|----------|------------|-------------|--------|
| 点击/拖拽 | ✅ | ✅ 已实现 | ADB | `action_executor.py` | - |
| 拟人化延迟 | ✅ | ✅ 已实现 | - | `action_executor.py:humanize` | - |
| 坐标配置 | ✅ | ✅ 已实现 | - | `config.example.yaml:coordinates` | - |
| 多分辨率适配 | ✅ | ❌ 缺失 | `3096-2064-500.exe` 命名 | 硬编码 1920x1080 | **P0** |

### 7. 日志/回放

| 功能 | S13福星版 | 当前状态 | 证据 (S13) | 证据 (当前) | 优先级 |
|------|-----------|----------|------------|-------------|--------|
| 操作日志 | ✅ | ✅ 已实现 | Qt5 | `logging` 模块 | - |
| 脚本录制 | ✅ | ❌ 缺失 | `config.ini:playback` | 无 | P2 |
| 脚本回放 | ✅ | ❌ 缺失 | `config.ini:playback` | 无 | P2 |
| 统计面板 | ✅ | ✅ 已实现 | Qt5 | `main.py:_print_stats()` | - |

### 8. 配置管理

| 功能 | S13福星版 | 当前状态 | 证据 (S13) | 证据 (当前) | 优先级 |
|------|-----------|----------|------------|-------------|--------|
| INI 配置 | ✅ | ⚠️ YAML | `config.ini` | `config.example.yaml` | - |
| 热键控制 | ✅ | ❌ 缺失 | `config.ini:start_key=F8` | 无 | P2 |
| CLI 参数 | ❌ | ✅ 已实现 | 无 | `main.py:argparse` | - |
| 环境变量 | ❌ | ✅ 已实现 | 无 | `main.py:os.getenv()` | - |

### 9. 分发/打包

| 功能 | S13福星版 | 当前状态 | 证据 (S13) | 证据 (当前) | 优先级 |
|------|-----------|----------|------------|-------------|--------|
| Windows EXE 打包 | ✅ | ❌ 缺失 | `*.exe` | 无 | P2 |
| 依赖捆绑 | ✅ | ❌ 缺失 | `*.dll` | 无 | P2 |
| 安装程序 | ❌ | ❌ 缺失 | 无 | 无 | P2 |

---

## 优先级队列

### P0 - 阻塞真实运行

| 缺口 | 影响 | 解决方案 | 状态 |
|------|------|----------|------|
| 模板匹配库缺失 | 无法识别游戏 UI 元素 | 从 S13 导入或新建模板库 | ✅ 基础完成 |
| 多分辨率适配 | 仅支持 1920x1080 | 动态坐标缩放 | ✅ 已解决 |
| Mac 窗口发现失败 | 无法定位游戏窗口 | --debug-window 已实现 | ✅ 已解决 |

### P1 - 影响可用性

| 缺口 | 影响 | 解决方案 | 状态 |
|------|------|----------|------|
| 实时截图预览 | 无法确认识别正确性 | TUI/Web 截图显示 | ⏳ 待实现 |
| 识别字段可视化 | 调试困难 | OCR 结果叠加显示 | ⏳ 待实现 |
| 动作队列显示 | 无法预知行为 | UI 队列组件 | ⏳ 待实现 |
| 英雄/装备/羁绊识别 | 仅靠 JSON 数据 | 模板库 + OCR | ⏳ 待实现 |

### P2 - 功能增强

| 缺口 | 影响 | 解决方案 | 状态 |
|------|------|----------|------|
| 桌面 GUI | 体验不如 Qt5 | Electron/Web | ⏳ 后续 |
| YOLO 目标检测 | 复杂场景识别弱 | 训练模型 | ⏳ 后续 |
| 热键控制 | 需 CLI 操作 | pynput 全局热键 | ⏳ 后续 |
| 脚本录制/回放 | 无法复现操作 | 录制 Action 序列 | ⏳ 后续 |
| Windows EXE 打包 | 需 Python 环境 | PyInstaller | ⏳ 后续 |

---

## 依赖关系图

```
[P0] 模板库├── [P1] 英雄识别
├── [P1] 装备识别
└── [P1] 羁绊识别

[P0] 多分辨率适配
└── [P1] 坐标自动缩放

[P0] 窗口调试 ✅
├── [P1] 截图预览
├── [P1] 识别可视化
└── [P1] 动作队列
```

---

## 当前迭代进度

| 任务 | 状态 | 提交 |
|------|------|------|
| LLM 可观测性 | ✅ 完成 | b04d32c |
| Gemini 接入 main.py | ✅ 完成 | b04d32c |
| dry-run 模式 | ✅ 完成 | b04d32c |
| --debug-window | ✅ 完成 | cc39d83 |
| --ui tui| ✅ 完成 | cc39d83 |
| 模板库建设 | ✅ 基础完成 | 814121a |
| 多分辨率适配 | ✅ 完成 | 814121a |

---

## 下一步行动

1. **模板库建设** — 从 S13 的 `script/image/` 导入模板，或新建
2. **多分辨率适配** — 实现坐标动态缩放
3. **TUI 截图预览** — 在 TUI 中显示最新截图（ASCII/Unicode art）

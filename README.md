# 金铲铲助手 (Jinchanchan Assistant)

AI 驱动的金铲铲之战（Teamfight Tactics）游戏助手，支持 Mac PlayCover 和 Windows 模拟器。

## 功能特性

- **双平台支持**：Mac PlayCover 和 Windows 模拟器
- **AI 决策**：集成 LLM（Claude/GPT-4o/通义千问）进行智能决策
- **规则引擎**：内置快速动作规则，无需 LLM 也能基本运行
- **视觉识别**：OCR + 模板匹配 + SoM 标注
- **拟人化操作**：随机延迟，降低检测风险

## 架构

```
jinchanchan-assistant/
├── core/                      # 核心引擎
│   ├── llm/                   # LLM 模块
│   ├── vision/                # 视觉识别
│   ├── rules/                 # 规则引擎
│   └── control/               # 动作执行
├── platforms/                 # 平台适配
│   ├── mac_playcover/         # Mac 适配器
│   └── windows_emulator/      # Windows 适配器
├── resources/                 # 资源文件
│   └── game_data/             # 游戏数据
└── config/                    # 配置文件
```

## 安装

### 1. 克隆项目

```bash
git clone https://github.com/your-repo/jinchanchan-assistant.git
cd jinchanchan-assistant
```

### 2. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
.\venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
# 基础依赖
pip install -e .

# Mac 平台额外依赖
pip install -e ".[mac]"

# Windows 平台额外依赖
pip install -e ".[windows]"

# 开发依赖
pip install -e ".[dev]"
```

### 4. 配置

复制配置文件并修改：

```bash
cp config/config.example.yaml config/config.yaml
```

编辑 `config/config.yaml` 设置你的 LLM API Key 和其他参数。

## 使用

### Mac PlayCover

```bash
# 纯规则模式（无需 LLM）
python main.py --platform mac

# 使用 Claude
python main.py --platform mac --llm-provider anthropic

# 使用 GPT-4o
python main.py --platform mac --llm-provider openai
```

### Windows 模拟器

```bash
# 确保模拟器已启动并开启 ADB 调试
python main.py --platform windows

# 指定模拟器端口
python main.py --platform windows --port 5555
```

### 命令行参数

| 参数 | 说明 | 默认值 |
|-----|------|-------|
| `--platform, -p` | 运行平台 (mac/windows) | mac |
| `--llm-provider` | LLM 提供商 | none |
| `--llm-model` | LLM 模型名称 | - |
| `--llm-api-key` | LLM API Key | - |
| `--interval, -i` | 决策间隔（秒） | 2.0 |
| `--verbose, -v` | 详细输出 | false |

## 环境变量

| 变量 | 说明 |
|-----|------|
| `ANTHROPIC_API_KEY` | Claude API Key |
| `OPENAI_API_KEY` | OpenAI API Key |
| `LLM_PROVIDER` | 默认 LLM 提供商 |
| `LLM_API_KEY` | 通用 LLM API Key |
| `LLM_MODEL` | 默认模型 |

## 开发

### 运行测试

```bash
pytest tests/
```

### 代码格式化

```bash
black .
ruff check .
```

### 类型检查

```bash
mypy .
```

## 技术栈

- **截图**：mss / Quartz.CoreGraphics
- **控制**：pyautogui / Quartz.CGEvent
- **OCR**：RapidOCR (PaddleOCR ONNX 版)
- **模板匹配**：OpenCV
- **LLM**：Anthropic Claude / OpenAI GPT-4o / 通义千问
- **决策**：混合架构（规则引擎 + LLM）

## 注意事项

1. **账号风险**：使用自动化工具存在账号被封的风险，请谨慎使用
2. **macOS 权限**：首次运行需要授权屏幕录制和辅助功能权限
3. **分辨率适配**：默认坐标基于 1920x1080，其他分辨率需要调整配置
4. **游戏更新**：游戏版本更新后可能需要更新模板和游戏数据

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 致谢

- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- [RapidOCR](https://github.com/RapidAI/RapidOCR)
- [Anthropic](https://www.anthropic.com/)
- [OpenAI](https://openai.com/)

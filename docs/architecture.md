# 金铲铲助手 - 系统架构

> 感知 → 状态 → 决策 → 执行 → 反馈

---

## 1. 架构概览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户层 (UI)                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                        │
│  │   CLI/TUI    │  │  (Future)    │  │  (Future)    │                        │
│  │   main.py    │  │   Web GUI    │  │  Desktop GUI │                        │
│  └──────────────┘  └──────────────┘  └──────────────┘                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            决策层 (Decision)                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐            │
│  │   RuleEngine     │  │  HybridEngine    │  │   LLMClient      │            │
│  │   (快速规则)     │  │  (规则+LLM融合)  │  │   (兜底决策)    │            │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘            │
│                                                                              │
│  输入: GameState  →  输出: DecisionResult (Action, confidence, source)        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            状态层 (State)                                     │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │                          GameState                                    │    │
│  │  • phase, round, stage                                               │    │
│  │  • gold, hp, level, exp                                               │    │
│  │  • heroes[], bench_heroes[], synergies{}, shop_slots[]                │    │
│  │  • available_items[]                                                  │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  输入: Screenshot + RecognitionResult  →  输出: GameState (更新后)            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            感知层 (Perception)                                │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐            │
│  │   OCREngine      │  │ TemplateMatcher  │  │ RecognitionEngine│            │
│  │   (文字识别)     │  │   (模板匹配)     │  │   (融合识别)    │            │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘            │
│                                                                              │
│  输入: Screenshot  →  输出: RecognizedEntity[]                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            执行层 (Execution)                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐            │
│  │  ActionExecutor  │  │ PlatformAdapter  │  │  ActionQueue     │            │
│  │   (动作执行)     │  │   (平台抽象)     │  │   (队列管理)    │            │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘            │
│                                                                              │
│  输入: Action  →  输出: ExecutionResult (success, error)                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            平台层 (Platform)                                  │
│  ┌──────────────────────────┐  ┌──────────────────────────┐                  │
│  │   MacPlayCoverAdapter    │  │  WindowsEmulatorAdapter  │                  │
│  │   (Quartz + mss)         │  │   (ADB + Win32)          │                  │
│  └──────────────────────────┘  └──────────────────────────┘                  │
│                                                                              │
│  契约: PlatformAdapter Protocol                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 模块边界与契约

### 2.1 PlatformAdapter Protocol

```python
class PlatformAdapter(Protocol):
    """平台适配器协议"""

    def get_window_info(self) -> WindowInfo | None:
        """获取游戏窗口信息"""
        ...

    def get_screenshot(self) -> Image.Image:
        """获取游戏截图"""
        ...

    def click(self, x: int, y: int, button: str = "left") -> bool:
        """点击坐标"""
        ...

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.3) -> bool:
        """拖拽"""
        ...

    def type_text(self, text: str) -> bool:
        """输入文本"""
        ...
```

### 2.2 GameState Schema

```python
@dataclass
class GameState:
    # 阶段
    phase: GamePhase          # loading/preparation/combat/carousel/settlement
    round_number: int
    stage: int

    # 资源
    gold: int
    hp: int
    level: int
    exp: int
    exp_to_level: int

    # 英雄
    heroes: list[Hero]        # 场上英雄 (最多 level 个)
    bench_heroes: list[Hero]  # 备战席 (最多 9 个)
    synergies: dict[str, Synergy]

    # 商店
    shop_slots: list[ShopSlot]  # 5 个槽位

    # 装备
    available_items: list[str]
```

### 2.3 Action Schema

```python
@dataclass
class Action:
    type: ActionType          # buy/sell/refresh/move/level_up/reroll/etc.
    target: str | None        # 目标英雄名/位置
    position: tuple[int, int] | None  # (row, col) 或 (bench_index,)
    metadata: dict[str, Any]

class ActionType(Enum):
    NONE = "none"
    BUY_HERO = "buy_hero"
    SELL_HERO = "sell_hero"
    MOVE_HERO = "move_hero"
    LEVEL_UP = "level_up"
    REFRESH_SHOP = "refresh_shop"
    BUY_EXP = "buy_exp"
```

### 2.4 DecisionResult

```python
@dataclass
class DecisionResult:
    action: Action
    source: str               # "rule" / "llm" / "hybrid"
    confidence: float         # 0.0 - 1.0
    reasoning: str | None     # LLM 决策时的推理过程
```

---

## 3. 数据流

### 3.1 主循环

```
┌─────────────────────────────────────────────────────────────────┐
│                        游戏主循环                                │
│                                                                  │
│   1. 截图: adapter.get_screenshot()                              │
│         ↓                                                        │
│   2. 识别: recognition_engine.recognize_shop/board/synergies()   │
│         ↓                                                        │
│   3. 状态更新: game_state.update_from_recognition()              │
│         ↓                                                        │
│   4. 决策: decision_engine.decide(game_state)                    │
│         ↓                                                        │
│   5. 执行: executor.execute(action)                              │
│         ↓                                                        │
│   6. 反馈: 记录结果，更新统计                                     │
│         ↓                                                        │
│   7. 等待: await sleep(interval)                                 │
│         ↓                                                        │
│   ┌───────────────────────────────────────────────┐              │
│   │              重复 1-7                         │              │
│   └───────────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 识别链路

```
Screenshot (PIL.Image)
    │
    ├─► regions.py (UI 区域定义)
    │       │
    │       ├─► shop_slots[0-4]
    │       ├─► board_cells[0-27]
    │       ├─► synergy_badges[0-9]
    │       └─► item_slots[0-9]
    │
    └─► RecognitionEngine
            │
            ├─► TemplateMatcher (模板匹配)
            │       └─► registry.json → templates/
            │
            ├─► OCREngine (文字识别)
            │       └─► RapidOCR / Tesseract / Vision
            │
            └─► _fuse_results (融合)
                    │
                    └─► RecognizedEntity[]
                            │
                            └─► GameState.update_from_recognition()
```

---

## 4. 能力分层

### 4.1 Lite Flavor (默认)

| 能力 | 依赖 | 判定条件 |
|------|------|----------|
| 平台适配 | mss, Quartz/ADB | ✅ 可导入 + 窗口/设备可发现 |
| 规则决策 | pydantic, yaml | ✅ 始终可用 |
| TUI | rich | ✅ 始终可用 |
| 模板注册表 | json | ✅ 始终可用 |

### 4.2 Full Flavor

| 能力 | 依赖 | 判定条件 |
|------|------|----------|
| Lite 全部 | - | ✅ |
| 模板匹配 | cv2, numpy | ✅ `import cv2` 成功 |
| OCR | rapidocr_onnxruntime | ✅ `import rapidocr_onnxruntime` 成功 |
| 识别引擎 | cv2 + ocr | ✅ 模板匹配 AND OCR 都可用 |
| LLM 决策 | anthropic/openai/gemini | ✅ 对应 API_KEY 环境变量已设置 |

---

## 5. 模块依赖图

```
main.py
    │
    ├── core/
    │   ├── game_state.py ────────► pydantic
    │   ├── action.py ────────────► pydantic
    │   ├── action_queue.py ──────► .
    │   ├── protocols.py ─────────► typing
    │   │
    │   ├── rules/
    │   │   ├── decision_engine.py ──► game_state, action, llm/client
    │   │   ├── quick_actions.py ────► game_state, action
    │   │   └── validator.py ────────► game_state, action
    │   │
    │   ├── llm/
    │   │   ├── client.py ──────────► anthropic/openai/google.genai
    │   │   ├── parser.py ──────────► .
    │   │   └── prompts.py ─────────► .
    │   │
    │   ├── vision/
    │   │   ├── ocr_engine.py ──────► rapidocr/tesseract/vision
    │   │   ├── template_matcher.py ► cv2, numpy
    │   │   ├── template_registry.py ► json, pathlib
    │   │   ├── regions.py ─────────► .
    │   │   └── recognition_engine.py ► ocr, template, registry, regions
    │   │
    │   ├── control/
    │   │   └── action_executor.py ─► protocols, action
    │   │
    │   └── ui/
    │       └── screenshot_renderer.py ► rich, PIL
    │
    └── platforms/
        ├── mac_playcover/
        │   ├── adapter.py ─────────► window_manager, Quartz
        │   └── window_manager.py ──► Quartz
        │
        └── windows_emulator/
            ├── adapter.py ─────────► adb_controller
            └── adb_controller.py ──► adb shell
```

---

## 6. 配置层次

```
优先级: CLI > 环境变量 > config.yaml > 默认值

config/
└── config.example.yaml
    ├── game:
    │   ├── decision_interval: 2.0
    │   └── dry_run_default: false
    │
    ├── platform:
    │   ├── type: "mac" | "windows"
    │   └── window_title: "金铲铲之战"
    │
    ├── llm:
    │   ├── provider: "anthropic" | "openai" | "gemini" | "none"
    │   ├── model: null
    │   ├── timeout: 30.0
    │   ├── max_retries: 2
    │   └── budget_per_session: 50
    │
    └── coordinates:
        └── (参考 1920x1080 坐标，运行时通过 CoordinateScaler 缩放)
```

---

## 7. 扩展点

| 扩展点 | 接口 | 实现 |
|--------|------|------|
| 新平台 | PlatformAdapter | 实现 protocol 方法 |
| 新 LLM | LLMClient | 添加 provider 枚举 + client 类 |
| 新识别器 | RecognitionEngine | 继承并重写 recognize_* 方法 |
| 新规则 | RuleEngine | 添加规则函数注册 |
| 新动作 | ActionType | 枚举 + ActionExecutor 分支 |

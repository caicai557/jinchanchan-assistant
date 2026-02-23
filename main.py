"""
Jinchanchan Assistant - Main Entry Point

AI-powered assistant for TFT (Teamfight Tactics), supporting Mac PlayCover and Windows emulator
"""

import argparse
import asyncio
import logging
import os
import platform
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any, TypedDict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import yaml

from core.action import ActionType
from core.action_queue import ActionQueue
from core.control.action_executor import ActionExecutor
from core.game_state import GamePhase, GameState
from core.llm.client import LLMClient, LLMConfig, LLMProvider
from core.protocols import PlatformAdapter
from core.rules.decision_engine import DecisionEngineBuilder
from core.vision.recognition_engine import create_recognition_engine


def get_version() -> str:
    """Get version from git tag or fallback to pyproject"""
    import subprocess

    # Try git describe --tags
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip().lstrip("v")
    except Exception:
        pass

    # Fallback to pyproject.toml
    try:
        import tomllib

        pyproject_path = Path(__file__).parent / "pyproject.toml"
        if pyproject_path.exists():
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
                project = data.get("project", {})
                version = project.get("version", "0.1.0")
                return str(version)
    except Exception:
        pass

    return "0.1.0"


# Version (read from git tag or pyproject.toml)
__version__ = get_version()


def setup_console_encoding() -> None:
    """
    Setup console encoding for Windows compatibility.

    Ensures UTF-8 output on Windows to avoid cp1252 UnicodeEncodeError.
    Call this as early as possible before any output.
    """
    # Set environment variables for child processes
    if not os.environ.get("PYTHONUTF8"):
        os.environ["PYTHONUTF8"] = "1"
    if not os.environ.get("PYTHONIOENCODING"):
        os.environ["PYTHONIOENCODING"] = "utf-8"

    # Reconfigure stdout/stderr for UTF-8 (Python 3.7+)
    if sys.platform == "win32":
        try:
            if sys.stdout and hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            if sys.stderr and hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass  # Best effort, don't crash on encoding setup


# Call encoding setup immediately
setup_console_encoding()


def get_capability_summary() -> dict[str, Any]:
    """
    Get capability summary (without importing heavy dependencies)

    Returns:
        Capability summary dict
    """
    capabilities: dict[str, Any] = {}

    # OCR availability (without importing onnxruntime)
    try:
        import rapidocr_onnxruntime  # noqa: F401

        capabilities["ocr"] = "rapidocr"
    except ImportError:
        try:
            import pytesseract  # noqa: F401

            capabilities["ocr"] = "tesseract"
        except ImportError:
            capabilities["ocr"] = "unavailable"

    # Template matching (OpenCV)
    try:
        import cv2  # noqa: F401

        capabilities["template_matching"] = "opencv"
    except ImportError:
        capabilities["template_matching"] = "unavailable"

    # LLM providers (check env only, no import)
    llm_available: list[str] = []
    if os.getenv("ANTHROPIC_API_KEY"):
        llm_available.append("anthropic")
    if os.getenv("OPENAI_API_KEY"):
        llm_available.append("openai")
    if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
        llm_available.append("gemini")
    capabilities["llm_configured"] = llm_available

    # Template count
    template_count = 0
    s13_templates = 0
    try:
        from core.vision.template_registry import TemplateRegistry

        registry = TemplateRegistry()
        registry.load_from_registry_json()
        template_count = len(registry._entries)
        s13_templates = registry.count_s13_imported()
    except Exception:
        pass

    # Platform adapter availability
    if platform.system() == "Darwin":
        try:
            from Quartz import CGWindowListCopyWindowInfo  # noqa: F401

            capabilities["mac_adapter"] = "available"
        except ImportError:
            capabilities["mac_adapter"] = "unavailable"
    elif platform.system() == "Windows":
        try:
            from platforms.windows_emulator import WindowsEmulatorAdapter  # noqa: F401

            capabilities["windows_adapter"] = "available"
        except ImportError:
            capabilities["windows_adapter"] = "unavailable"

    return {
        "version": __version__,
        "platform": platform.system(),
        "python": platform.python_version(),
        "capabilities": capabilities,
        "template_count": template_count,
        "s13_templates": s13_templates,
    }


def format_capability_summary() -> str:
    """Format capability summary as readable string (ASCII only for Windows compatibility)"""
    from core.capabilities import get_capability_matrix

    matrix = get_capability_matrix()
    cap = get_capability_summary()

    lines = [
        f"=== Jinchanchan Assistant v{__version__} [{matrix.flavor.value.upper()}] ===",
        f"Platform: {cap['platform']} | Python: {cap['python']}",
        "",
        matrix.format_summary_ascii(),
    ]

    return "\n".join(lines)


class TUIState(TypedDict):
    """TUI 状态"""

    last_screenshot: Any  # PIL.Image.Image | None
    last_action: str
    last_source: str
    last_confidence: float
    action_queue: ActionQueue


def run_doctor() -> int:
    """
    Run diagnostics and print troubleshooting suggestions

    Returns:
        0 if all checks pass, 1 if any issues found
    """
    import subprocess

    from core.vision.regions import GameRegions

    print("=== Jinchanchan Assistant Doctor ===")
    print()

    issues = []

    # 1. Platform check
    print("[1/6] Platform")
    print(f"  OS: {platform.system()}")
    print(f"  Python: {platform.python_version()}")
    print(f"  Architecture: {platform.machine()}")
    print()

    # 2. Platform adapter
    print("[2/6] Platform Adapter")
    if platform.system() == "Darwin":
        try:
            from Quartz import CGWindowListCopyWindowInfo  # noqa: F401

            print("  [OK] Quartz available")
        except ImportError:
            print("  [FAIL] Quartz not available")
            print("  FIX: pip install pyobjc-framework-Quartz")
            issues.append("quartz")
    elif platform.system() == "Windows":
        # Check ADB
        try:
            result = subprocess.run(
                ["adb", "version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                ver = result.stdout.split()
                ver_str = ver[4] if len(ver) > 4 else "available"
                print(f"  [OK] ADB: {ver_str}")
            else:
                print("  [FAIL] ADB not working")
                print("  FIX: Install Android Platform Tools")
                issues.append("adb")
        except FileNotFoundError:
            print("  [FAIL] ADB not found in PATH")
            print("  FIX: Add ADB to PATH or install platform-tools")
            issues.append("adb")
        except Exception as e:
            print(f"  [FAIL] ADB error: {e}")
            issues.append("adb")
    print()

    # 3. Template registry
    print("[3/6] Template Registry")
    try:
        from core.vision.template_registry import TemplateRegistry

        registry = TemplateRegistry()
        count = registry.load_from_registry_json()
        s13_count = registry.count_s13_imported()
        if count > 0:
            print(f"  [OK] {count} templates loaded ({s13_count} S13)")
        else:
            print("  [WARN] No templates loaded")
            print("  FIX: Check resources/templates/registry.json")
    except Exception as e:
        print(f"  [FAIL] {e}")
        issues.append("templates")
    print()

    # 4. OCR backend
    print("[4/6] OCR Backend")
    try:
        import rapidocr_onnxruntime  # noqa: F401

        print("  [OK] RapidOCR available")
    except ImportError:
        print("  [WARN] RapidOCR not available")
        print("  FIX: pip install rapidocr-onnxruntime (for Full flavor)")

    try:
        import pytesseract  # noqa: F401

        print("  [OK] Tesseract available (fallback)")
    except ImportError:
        pass
    print()

    # 5. Template matching (OpenCV)
    print("[5/6] Template Matching")
    try:
        import cv2  # noqa: F401

        print(f"  [OK] OpenCV: {cv2.__version__}")
    except ImportError:
        print("  [WARN] OpenCV not available")
        print("  FIX: pip install opencv-python-headless (for Full flavor)")
    print()

    # 6. Window/Device check
    print("[6/6] Window/Device")
    doctor_transform = GameRegions.create_transform(GameRegions.BASE_SIZE)
    if platform.system() == "Darwin":
        try:
            from platforms.mac_playcover.window_manager import WindowManager

            wm = WindowManager()
            window = wm.find_game_window()
            if window:
                print("  [OK] Game window found")
                print(f"       - {window.title} ({window.width}x{window.height})")
                doctor_transform = GameRegions.create_transform((window.width, window.height))
            else:
                print("  [WARN] No game windows found")
                print("  FIX: Start the game first")
        except Exception as e:
            print(f"  [FAIL] {e}")
            issues.append("window")
    elif platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            lines = result.stdout.strip().split("\n")
            devices = [line.split()[0] for line in lines[1:] if line.strip() and "\tdevice" in line]
            if devices:
                print(f"  [OK] {len(devices)} device(s) connected")
                for d in devices:
                    print(f"       - {d}")
            else:
                print("  [WARN] No devices connected")
                print("  FIX: Start emulator and run: adb connect 127.0.0.1:5555")
        except Exception as e:
            print(f"  [FAIL] {e}")
            issues.append("device")
    diag = doctor_transform.diagnostics()
    scale_x, scale_y = doctor_transform.scale
    offset = doctor_transform.offset
    content_rect = doctor_transform.content_rect_or_full()
    print(
        "  [INFO] Transform:"
        f" base={diag['base_size']}"
        f" current={diag['current_size']}"
        f" scale=({scale_x:.4f}, {scale_y:.4f})"
        f" offset={offset}"
        f" content_rect={content_rect}"
    )
    print()

    # Summary
    print("=" * 40)
    if issues:
        print(f"RESULT: ISSUES FOUND ({len(issues)})")
        print("Please fix the issues above and run --doctor again.")
        return 1
    else:
        print("RESULT: ALL CHECKS PASSED")
        print("Ready to run!")
        return 0


# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("jinchanchan")


def configure_file_logging(log_file: str) -> Path:
    """强制追加文件日志（artifacts 证据）。"""
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    resolved = log_path.resolve()
    for handler in root_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            try:
                if Path(handler.baseFilename).resolve() == resolved:
                    return log_path
            except Exception:
                continue

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(root_logger.level)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root_logger.addHandler(file_handler)
    return log_path


class JinchanchanAssistant:
    """
    金铲铲助手主类

    整合所有模块，实现完整的游戏自动化流程
    """

    def __init__(
        self,
        platform_adapter: PlatformAdapter,
        llm_client: LLMClient | None = None,
        decision_interval: float = 2.0,
        dry_run: bool = False,
        max_actions_per_min: int | None = None,
        max_clicks: int | None = None,
        timeout: float | None = None,
        llm_budget: int | None = None,
    ):
        self.adapter = platform_adapter
        self.llm_client = llm_client
        self.decision_interval = decision_interval
        self.dry_run = dry_run
        self.max_actions_per_min = max_actions_per_min
        self.max_clicks = max_clicks
        self.timeout = timeout
        self.llm_budget = llm_budget

        # 初始化决策引擎
        engine_builder = DecisionEngineBuilder()
        if llm_client:
            engine_builder.with_llm(llm_client)
        self.decision_engine = engine_builder.build()

        # 初始化动作执行器
        self.executor = ActionExecutor(self.adapter)
        self.executor.auto_detect_resolution()

        # 初始化识别引擎
        self.recognition_engine = create_recognition_engine()

        # 状态
        self._running = False
        self._game_state = GameState()
        self._session_started_monotonic = time.monotonic()
        self._timeout_warning_emitted = False
        self._action_timestamps: deque[float] = deque()
        self._click_count = 0
        self._recognition_warning_every = 5

        # 统计
        self._stats = {
            "total_decisions": 0,
            "actions_executed": 0,
            "errors": 0,
            "recognition_errors": 0,
            "safety_blocks": 0,
        }

    async def run(self) -> None:
        """运行助手"""
        logger.info("金铲铲助手启动")
        self._running = True
        self._session_started_monotonic = time.monotonic()

        try:
            while self._running:
                await self._game_loop()
                await asyncio.sleep(self.decision_interval)
        except KeyboardInterrupt:
            logger.info("收到中断信号，停止运行")
        except Exception as e:
            logger.error(f"运行出错: {e}")
        finally:
            self._running = False
            self._print_stats()

    def _check_timeout(self) -> bool:
        """检查运行超时；超时时停止主循环。"""
        if self.timeout is None or self.timeout <= 0:
            return False

        elapsed = time.monotonic() - self._session_started_monotonic
        if elapsed < self.timeout:
            return False

        if not self._timeout_warning_emitted:
            self._timeout_warning_emitted = True
            logger.warning(
                "达到运行超时上限，停止运行: elapsed=%.1fs timeout=%.1fs",
                elapsed,
                self.timeout,
            )
        self._running = False
        return True

    def _run_recognition_step(self, screenshot: Any) -> dict[str, int | None]:
        """执行识别并写回 game_state，返回用于日志的关键字段。"""
        fields: dict[str, int | None] = {
            "gold": None,
            "level": None,
            "shop_count": None,
        }
        try:
            # 点击坐标按窗口尺寸刷新，识别坐标按截图尺寸在 recognition_engine 内部更新
            self.executor.auto_detect_resolution()

            shop = self.recognition_engine.recognize_shop(screenshot)
            bench = self.recognition_engine.recognize_bench(screenshot)
            self._game_state.update_from_recognition(
                shop_entities=shop,
                bench_entities=bench,
            )
            recognized = sum(1 for s in shop if s is not None)
            fields["shop_count"] = recognized
            if recognized:
                logger.debug("识别到 %d 个商店英雄", recognized)
                self._game_state.phase = GamePhase.PREPARATION

            info = self.recognition_engine.recognize_player_info(screenshot)
            fields["gold"] = info.get("gold")
            fields["level"] = info.get("level")
            if fields["gold"] is not None:
                self._game_state.gold = fields["gold"]
            if fields["level"] is not None:
                self._game_state.level = fields["level"]
        except Exception as e:
            self._stats["recognition_errors"] += 1
            count = self._stats["recognition_errors"]
            if count % self._recognition_warning_every == 0:
                logger.warning("识别异常已累计 %d 次，最近一次: %s", count, e)
            else:
                logger.debug("识别跳过(%d): %s", count, e)
        return fields

    def _log_loop_observation(
        self,
        screenshot: Any,
        recognition_fields: dict[str, int | None],
        action_type: str,
    ) -> None:
        """记录每轮关键观测信息，便于 live 回归。"""
        scale_x = scale_y = 1.0
        offset = (0, 0)
        try:
            transform = self.recognition_engine.transform
            scale_x, scale_y = transform.scale
            offset = transform.offset
        except Exception:
            pass

        logger.info(
            (
                "loop window_size=%sx%s scale=(%.4f,%.4f) offset=%s "
                "gold=%s level=%s shop_count=%s action=%s"
            ),
            getattr(screenshot, "width", "?"),
            getattr(screenshot, "height", "?"),
            scale_x,
            scale_y,
            offset,
            recognition_fields.get("gold"),
            recognition_fields.get("level"),
            recognition_fields.get("shop_count"),
            action_type,
        )

    def _can_execute_live_action(self) -> tuple[bool, str | None]:
        """检查 live 模式安全闸。"""
        if self.dry_run:
            return (True, None)

        now = time.monotonic()
        if self.max_actions_per_min is not None and self.max_actions_per_min > 0:
            while self._action_timestamps and (now - self._action_timestamps[0]) > 60:
                self._action_timestamps.popleft()
            if len(self._action_timestamps) >= self.max_actions_per_min:
                return (
                    False,
                    (
                        "触发速率限制: "
                        f"{len(self._action_timestamps)}/{self.max_actions_per_min} actions/min"
                    ),
                )

        if (
            self.max_clicks is not None
            and self.max_clicks > 0
            and self._click_count >= self.max_clicks
        ):
            return (False, f"触发点击上限: {self._click_count}/{self.max_clicks}")

        return (True, None)

    def _record_live_action_execution(self) -> None:
        """记录 live 模式动作执行计数。"""
        if self.dry_run:
            return
        self._action_timestamps.append(time.monotonic())
        self._click_count += 1

    async def _game_loop(self) -> None:
        """游戏主循环"""
        try:
            if self._check_timeout():
                return

            # 1. 获取游戏截图
            screenshot = self.adapter.get_screenshot()
            logger.debug("获取截图成功")

            # 2. 视觉识别 → 更新游戏状态
            recognition_fields = self._run_recognition_step(screenshot)

            # 3. 决策
            result = await self.decision_engine.decide(
                screenshot=screenshot, game_state=self._game_state, priority="balanced"
            )

            self._stats["total_decisions"] += 1
            self._log_loop_observation(screenshot, recognition_fields, result.action.type.value)
            logger.info(
                f"决策结果: {result.action.type.value} "
                f"(来源: {result.source}, 置信度: {result.confidence:.2f})"
            )

            # 3. 执行动作
            if result.action.type != ActionType.NONE:
                if self.dry_run:
                    logger.info(f"[dry-run] 跳过执行: {result.action.type.value}")
                else:
                    allowed, reason = self._can_execute_live_action()
                    if not allowed:
                        self._stats["safety_blocks"] += 1
                        logger.warning("安全闸阻止动作 %s: %s", result.action.type.value, reason)
                        return

                    self._record_live_action_execution()
                    exec_result = await self.executor.execute(result.action)

                    if exec_result.success:
                        self._stats["actions_executed"] += 1
                        logger.info(f"执行成功: {result.action.type.value}")
                    else:
                        logger.warning(f"执行失败: {exec_result.error}")

                    await asyncio.sleep(0.5)
            else:
                # NONE 也要有每轮日志，已在 _log_loop_observation 输出
                pass

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"游戏循环出错: {e}")

    def stop(self) -> None:
        """停止助手"""
        self._running = False

    def _print_stats(self) -> None:
        """打印统计信息"""
        logger.info("===== 运行统计 =====")
        logger.info(f"总决策次数: {self._stats['total_decisions']}")
        logger.info(f"执行动作次数: {self._stats['actions_executed']}")
        logger.info(f"错误次数: {self._stats['errors']}")
        logger.info(f"识别异常次数: {self._stats['recognition_errors']}")
        logger.info(f"安全闸阻止次数: {self._stats['safety_blocks']}")
        logger.info(f"点击计数: {self._click_count}")

        decision_stats = self.decision_engine.get_stats()
        logger.info(f"规则决策: {decision_stats.get('rule_decisions', 0)}")
        logger.info(f"LLM 决策: {decision_stats.get('llm_decisions', 0)}")

        executor_stats = self.executor.get_stats()
        logger.info(f"成功执行: {executor_stats.get('successful_actions', 0)}")
        logger.info(f"失败执行: {executor_stats.get('failed_actions', 0)}")


def create_platform_adapter(platform: str, **kwargs) -> PlatformAdapter:
    """
    创建平台适配器

    Args:
        platform: 平台名称 ("mac" 或 "windows")
        **kwargs: 额外参数

    Returns:
        PlatformAdapter 实例
    """
    if platform == "mac":
        from platforms.mac_playcover import MacPlayCoverAdapter

        return MacPlayCoverAdapter(window_title=kwargs.get("window_title", "金铲铲之战"))
    elif platform == "windows":
        from platforms.windows_emulator import WindowsEmulatorAdapter

        return WindowsEmulatorAdapter(
            adb_path=kwargs.get("adb_path", "adb"), port=kwargs.get("port", 5555)
        )
    else:
        raise ValueError(f"不支持的平台: {platform}")


def create_llm_client(
    provider: str,
    model: str | None = None,
    timeout: float = 30.0,
    max_retries: int = 2,
    budget: int = 50,
    enable_logging: bool = False,
) -> LLMClient | None:
    if provider == "none":
        return None

    try:
        provider_enum = LLMProvider(provider)
        default_model = LLMConfig.DEFAULT_MODELS.get(provider_enum, "")

        return LLMClient(
            LLMConfig(
                provider=provider_enum,
                api_key=os.getenv(f"{provider.upper()}_API_KEY") or os.getenv("LLM_API_KEY"),
                model=model or default_model or "",
                timeout=timeout,
                max_retries=max_retries,
                budget_per_session=budget,
                enable_logging=enable_logging,
            )
        )
    except Exception as e:
        logger.warning(f"创建 LLM 客户端失败: {e}")
        return None


def load_config(path: str = "config/config.yaml") -> dict[str, Any]:
    """加载 YAML 配置，不存在则返回空 dict。"""
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


async def run_offline_replay_test_async() -> int:
    """
    运行离线回放自检测试 (async 版本)

    使用内置 fixtures 执行 vision->state->decision 链路
    生成 replay_results.json 作为证据

    Returns:
        0 表示成功，非零表示失败
    """
    import json
    import random
    from pathlib import Path

    from PIL import Image

    from core.action import Action, ActionType
    from core.game_state import GameState
    from core.rules.decision_engine import DecisionEngineBuilder
    from core.rules.validator import ActionValidator
    from core.vision.regions import GameRegions, UIRegion

    print("=== 离线回放自检测试 ===")
    print()

    seed = 42
    random.seed(seed)

    # 初始化组件
    decision_engine = DecisionEngineBuilder().with_llm_fallback(enabled=False).build()
    validator = ActionValidator()

    # 查找 fixtures 目录
    possible_paths = [
        Path(__file__).parent / "tests" / "fixtures" / "screens",
        Path(__file__).parent.parent / "tests" / "fixtures" / "screens",
        Path("tests/fixtures/screens"),
        Path("/app/tests/fixtures/screens"),  # PyInstaller 打包后
    ]

    fixtures_dir = None
    for p in possible_paths:
        if p.exists() and list(p.glob("*.png")):
            fixtures_dir = p
            break

    if not fixtures_dir:
        print("[ERROR] 未找到 fixtures 目录")
        print(f"搜索路径: {[str(p) for p in possible_paths]}")
        return 1

    print(f"Fixtures 目录: {fixtures_dir}")

    # 提取字段
    def extract_fields(screenshot: Image.Image) -> dict:
        extracted = {}
        transform = GameRegions.create_transform(screenshot.size)

        def crop_to_base(base_region: UIRegion) -> Image.Image:
            current_region = base_region.scale(transform)
            cropped = screenshot.crop(current_region.bbox)
            if cropped.size == (base_region.width, base_region.height):
                return cropped
            return cropped.resize((base_region.width, base_region.height), Image.NEAREST)

        # 分析顶部区域
        top_base = UIRegion(
            name="replay_top_bar",
            x=0,
            y=0,
            width=GameRegions.BASE_SIZE[0],
            height=60,
        )
        top_region = crop_to_base(top_base)
        top_pixels = list(top_region.getdata())

        # 检测金币
        gold_pixels = sum(1 for p in top_pixels if p[1] > 200 and p[2] < 100)
        extracted["gold"] = min(gold_pixels // 100, 100)

        slot_colors = [
            (80, 160, 80),
            (80, 80, 160),
            (160, 80, 160),
            (160, 120, 80),
            (200, 160, 80),
        ]

        detected_slots = 0
        for slot_region in GameRegions.all_shop_slots():
            slot_image = crop_to_base(slot_region)
            slot_pixels = list(slot_image.getdata())
            has_slot_color = any(
                sum(
                    1
                    for p in slot_pixels
                    if abs(p[0] - color[0]) < 30
                    and abs(p[1] - color[1]) < 30
                    and abs(p[2] - color[2]) < 30
                )
                > 80
                for color in slot_colors
            )
            if has_slot_color:
                detected_slots += 1

        extracted["shop_slots"] = min(detected_slots, 5)
        extracted["round_number"] = 1
        extracted["level"] = 1
        extracted["hp"] = 100

        return extracted

    results = []
    fixtures = sorted(fixtures_dir.glob("*.png"))

    print(f"发现 {len(fixtures)} 个 fixtures")
    print()

    for fixture in fixtures:
        print(f"测试: {fixture.name}")

        # 加载截图
        screenshot = Image.open(fixture)

        # 提取字段
        extracted = extract_fields(screenshot)

        # 更新游戏状态
        game_state = GameState()
        game_state.gold = extracted.get("gold", 0)
        game_state.level = extracted.get("level", 1)

        # 生成动作 (直接 await，不嵌套 asyncio.run)
        actions = []
        decision_result = await decision_engine.decide(screenshot, game_state)
        if decision_result and decision_result.action:
            actions.append(decision_result.action)
        if not actions:
            actions.append(Action(type=ActionType.NONE, confidence=1.0))

        # 验证动作
        validation_passed = all(validator.validate(action, game_state) for action in actions)

        fixture_result = {
            "fixture": fixture.name,
            "extracted_fields": extracted,
            "actions": [
                {"type": a.type.value, "target": a.target, "confidence": a.confidence}
                for a in actions
            ],
            "validation_passed": validation_passed,
        }
        results.append(fixture_result)

        status = "PASS" if validation_passed else "FAIL"
        print(f"  提取字段: {list(extracted.keys())}")
        print(f"  动作数量: {len(actions)}")
        print(f"  验证: {status}")
        print()

    # 生成报告
    output_path = Path("replay_results.json")
    report = {
        "version": "1.0",
        "seed": seed,
        "fixtures_tested": len(results),
        "all_passed": all(r["validation_passed"] for r in results),
        "results": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"报告已保存: {output_path}")
    print()

    # 最终判定
    all_passed = all(r["validation_passed"] for r in results)
    if all_passed:
        print("=== 自检结果: PASS ===")
        return 0
    else:
        print("=== 自检结果: FAIL ===")
        return 1


def run_offline_replay_test() -> int:
    """
    运行离线回放自检测试 (同步入口)

    使用内置 fixtures 执行 vision->state->decision 链路
    生成 replay_results.json 作为证据

    Returns:
        0 表示成功，非零表示失败
    """
    import asyncio

    return asyncio.run(run_offline_replay_test_async())


def debug_windows(
    platform: str = "mac",
    filter_pattern: str | None = None,
    use_regex: bool = False,
    game_names: list[str] | None = None,
) -> int:
    """
    调试窗口发现，输出所有候选窗口信息

    Args:
        platform: 平台
        filter_pattern: 过滤模式
        use_regex: 是否正则匹配
        game_names: 游戏名称列表

    Returns:
        退出码
    """
    if platform != "mac":
        logger.error("--debug-window 仅支持 mac 平台")
        return 1

    try:
        from platforms.mac_playcover.window_manager import WindowManager
    except ImportError as e:
        logger.error(f"无法加载 WindowManager: {e}")
        return 1

    wm = WindowManager()
    windows = wm.enumerate_windows(
        filter_pattern=filter_pattern,
        use_regex=use_regex,
        visible_only=True,
    )

    print("\n=== 窗口枚举结果 ===")
    print(f"{'标题':<30} {'进程':<20} {'PID':>7} {'WID':>7} {'可见':>4} {'尺寸':<15}")
    print("-" * 95)

    for w in windows:
        title = w["title"][:28] + "..." if len(w["title"]) > 30 else w["title"]
        owner = w["owner"][:18] + "..." if len(w["owner"]) > 20 else w["owner"]
        size = f"{w['width']}x{w['height']}"
        print(
            f"{title:<30} {owner:<20} {w['pid']:>7} {w['window_id']:>7} "
            f"{'✓' if w['visible'] else '✗':>4} {size:<15}"
        )

    print(f"\n共 {len(windows)} 个窗口")

    # 检查游戏窗口匹配
    if game_names is None:
        game_names = ["金铲铲之战", "金铲铲", "TFT", "Teamfight Tactics"]

    print("\n=== 游戏窗口匹配 ===")
    for name in game_names:
        win = wm.find_window_by_title(name)
        if win:
            print(f"✓ 找到: '{name}' -> {win.title} ({win.width}x{win.height})")
        else:
            print(f"✗ 未找到: '{name}'")

    return 0


def run_tui(
    adapter: PlatformAdapter,
    llm_client: LLMClient | None,
    dry_run: bool,
    interval: float,
    budget: int,
    max_actions_per_min: int | None = None,
    max_clicks: int | None = None,
    timeout: float | None = None,
) -> int:
    """
    运行 TUI 界面

    Args:
        adapter: 平台适配器
        llm_client: LLM 客户端
        dry_run: 是否只读模式
        interval: 决策间隔
        budget: LLM 预算
        max_actions_per_min: 每分钟动作上限（live）
        max_clicks: 点击上限（live）
        timeout: 运行超时（秒）

    Returns:
        退出码
    """
    try:
        from rich.console import Console
        from rich.layout import Layout
        from rich.live import Live
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
    except ImportError:
        print("TUI 需要 rich 库: pip install rich")
        return 1

    from core.ui.screenshot_renderer import ScreenshotRenderer

    console = Console()
    screenshot_renderer = ScreenshotRenderer(width=50, use_color=True)

    assistant = JinchanchanAssistant(
        platform_adapter=adapter,
        llm_client=llm_client,
        decision_interval=interval,
        dry_run=dry_run,
        max_actions_per_min=max_actions_per_min,
        max_clicks=max_clicks,
        timeout=timeout,
        llm_budget=budget,
    )

    # 存储最新截图和识别结果
    action_queue = ActionQueue(max_history=50)
    state: TUIState = {
        "last_screenshot": None,
        "last_action": "等待中...",
        "last_source": "-",
        "last_confidence": 0.0,
        "action_queue": action_queue,
    }

    def build_stats_panel() -> Panel:
        """构建统计面板"""
        stats = assistant._stats
        engine_stats = assistant.decision_engine.get_stats()
        llm_calls = llm_client._call_count if llm_client else 0

        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("key", style="cyan", width=12)
        table.add_column("value", style="green")

        mode_text = "[red]DRY-RUN[/red]" if dry_run else "[green]LIVE[/green]"
        table.add_row("模式", mode_text)
        table.add_row("决策", str(stats["total_decisions"]))
        table.add_row("执行", str(stats["actions_executed"]))
        table.add_row("错误", str(stats["errors"]))
        table.add_row("识别异常", str(stats["recognition_errors"]))
        table.add_row("安全闸", str(stats["safety_blocks"]))
        table.add_row("规则", str(engine_stats.get("rule_decisions", 0)))
        table.add_row("LLM", str(engine_stats.get("llm_decisions", 0)))
        table.add_row("Budget", f"{llm_calls}/{budget}")

        window_info = adapter.get_window_info()
        if window_info:
            table.add_row("窗口", f"{window_info.width}x{window_info.height}")
        else:
            table.add_row("窗口", "[red]未找到[/red]")

        return Panel(table, title="📊 状态", border_style="blue")

    def build_action_panel() -> Panel:
        """构建动作面板"""
        content = Text()
        content.append("最后动作: ", style="cyan")
        content.append(f"{state['last_action']}\n", style="yellow")
        content.append("来源: ", style="cyan")
        content.append(f"{state['last_source']}\n", style="green")
        content.append("置信度: ", style="cyan")
        content.append(f"{state['last_confidence']:.2f}")
        return Panel(content, title="🎯 决策", border_style="green")

    def build_queue_panel() -> Panel:
        """构建动作队列面板"""
        queue = state["action_queue"]
        pending = queue.get_pending()
        history = queue.get_history(limit=3)

        lines = []

        # 当前执行
        current = queue.get_current()
        if current:
            lines.append("[bold yellow]▶ 执行中:[/bold yellow]")
            lines.append(f"  {current.action.type.value}")

        # 待执行
        if pending:
            lines.append(f"[bold cyan]⏳ 待执行 ({len(pending)}):[/bold cyan]")
            for qa in pending[:4]:
                target = f" → {qa.action.target}" if qa.action.target else ""
                lines.append(f"  • {qa.action.type.value}{target}")
            if len(pending) > 4:
                lines.append(f"  [dim]... +{len(pending) - 4}[/dim]")

        # 最近完成
        if history:
            lines.append("[bold green]✓ 已完成:[/bold green]")
            for qa in history[:3]:
                icon = "✓" if qa.status == "completed" else "✗"
                color = "green" if qa.status == "completed" else "red"
                lines.append(f"  [{color}]{icon}[/{color}] {qa.action.type.value}")

        if not lines:
            return Panel("[dim]队列为空[/dim]", title="📋 动作队列", border_style="magenta")

        return Panel("\n".join(lines), title="📋 动作队列", border_style="magenta")

    def build_screenshot_panel() -> Panel:
        """构建截图面板"""
        if state["last_screenshot"] is not None:
            try:
                rendered = screenshot_renderer.render(state["last_screenshot"])
                return Panel(rendered, title="📸 截图预览", border_style="yellow")
            except Exception:
                return Panel("[dim]渲染失败[/dim]", title="📸 截图预览", border_style="yellow")
        else:
            return Panel("[dim]等待截图...[/dim]", title="📸 截图预览", border_style="yellow")

    def build_ui() -> Layout:
        """构建完整 UI 布局"""
        layout = Layout()

        layout.split_column(
            Layout(name="body", ratio=1),
        )

        layout["body"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=2),
        )

        layout["left"].split_column(
            Layout(build_stats_panel(), name="stats", ratio=2),
            Layout(build_action_panel(), name="action", ratio=1),
            Layout(build_queue_panel(), name="queue", ratio=2),
        )

        layout["right"].update(build_screenshot_panel())

        return layout

    async def game_loop_with_screenshot() -> None:
        """带截图保存的游戏循环"""
        try:
            if assistant._check_timeout():
                return

            # 获取截图
            screenshot = adapter.get_screenshot()
            state["last_screenshot"] = screenshot

            # 识别并更新状态
            recognition_fields = assistant._run_recognition_step(screenshot)

            # 决策
            result = await assistant.decision_engine.decide(
                screenshot=screenshot,
                game_state=assistant._game_state,
                priority="balanced",
            )

            assistant._stats["total_decisions"] += 1

            # 更新状态
            state["last_action"] = result.action.type.value
            state["last_source"] = result.source
            state["last_confidence"] = result.confidence

            assistant._log_loop_observation(
                screenshot,
                recognition_fields,
                result.action.type.value,
            )
            logger.info(
                f"决策: {result.action.type.value} (来源: {result.source}, "
                f"置信度: {result.confidence:.2f})"
            )

            # 执行动作
            if result.action.type != ActionType.NONE:
                # 加入队列
                queue = state["action_queue"]
                queue.enqueue(result.action)

                if assistant.dry_run:
                    logger.info(f"[dry-run] 跳过: {result.action.type.value}")
                    queue.complete_current(success=True)
                else:
                    allowed, reason = assistant._can_execute_live_action()
                    if not allowed:
                        assistant._stats["safety_blocks"] += 1
                        logger.warning("安全闸阻止动作 %s: %s", result.action.type.value, reason)
                        queue.complete_current(success=False, error=reason)
                        return

                    assistant._record_live_action_execution()
                    # 取出并执行
                    to_execute = queue.dequeue()
                    if to_execute:
                        exec_result = await assistant.executor.execute(to_execute.action)

                        if exec_result.success:
                            assistant._stats["actions_executed"] += 1
                            logger.info(f"执行成功: {result.action.type.value}")
                            queue.complete_current(success=True)
                        else:
                            logger.warning(f"执行失败: {exec_result.error}")
                            queue.complete_current(success=False, error=exec_result.error)

                    await asyncio.sleep(0.5)

        except Exception as e:
            assistant._stats["errors"] += 1
            logger.error(f"游戏循环出错: {e}")

    async def run_with_ui() -> None:
        """带 UI 的运行循环"""
        console.print("[bold green]启动 TUI 模式，按 Ctrl+C 退出[/bold green]")
        console.print(f"[cyan]dry_run={dry_run} budget={budget}[/cyan]")

        assistant._running = True
        assistant._session_started_monotonic = time.monotonic()
        try:
            with Live(build_ui(), console=console, refresh_per_second=2, screen=True):
                while assistant._running:
                    await game_loop_with_screenshot()
                    await asyncio.sleep(interval)
        except KeyboardInterrupt:
            assistant._running = False
        finally:
            assistant._print_stats()

    asyncio.run(run_with_ui())
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(description="Jinchanchan Assistant")
    parser.add_argument(
        "--version", "-V", action="store_true", default=False, help="Show version and capabilities"
    )
    parser.add_argument(
        "--capabilities",
        action="store_true",
        default=False,
        help="Show capability summary and exit",
    )
    parser.add_argument(
        "--require-full",
        action="store_true",
        default=False,
        help="Require Full flavor, exit non-zero if capabilities missing",
    )
    parser.add_argument(
        "--self-test",
        choices=["offline-replay"],
        default=None,
        help="Run self-test and generate replay_results.json",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        default=False,
        help="Run diagnostics and print troubleshooting suggestions",
    )

    parser.add_argument("--platform", "-p", choices=["mac", "windows"], default="mac")
    parser.add_argument(
        "--llm-provider",
        choices=["anthropic", "openai", "qwen", "gemini", "none"],
        default=None,
    )
    parser.add_argument("--llm-model", default=None)
    parser.add_argument("--llm-timeout", type=float, default=None)
    parser.add_argument("--llm-retries", type=int, default=None)
    parser.add_argument("--llm-budget", type=int, default=None)
    parser.add_argument("--llm-log", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--max-actions-per-min", type=int, default=None)
    parser.add_argument("--max-clicks", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=None, help="Session timeout in seconds")
    parser.add_argument("--log-file", default="artifacts/local/run.log")
    parser.add_argument("--interval", "-i", type=float, default=2.0)
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument(
        "--debug-window",
        action="store_true",
        default=False,
        help="Enumerate and print candidate windows (mac only)",
    )
    parser.add_argument(
        "--window-filter",
        default=None,
        help="Window filter pattern (contains or regex with --window-regex)",
    )
    parser.add_argument(
        "--window-regex",
        action="store_true",
        default=False,
        help="Use regex for window filter",
    )
    parser.add_argument(
        "--ui",
        choices=["none", "tui"],
        default="none",
        help="UI mode (default: none)",
    )

    args = parser.parse_args()

    log_path = configure_file_logging(args.log_file)
    logger.info("日志落盘路径: %s", log_path)

    # --version 或 --capabilities: 输出能力摘要并退出
    if args.version or args.capabilities:
        print(format_capability_summary())

        # --require-full: 检查 Full 能力
        if args.require_full:
            from core.capabilities import get_capability_matrix

            matrix = get_capability_matrix()
            if not matrix.is_full():
                print("\n[ERROR] Full 能力检查失败:")
                for name, result in matrix._results.items():
                    if result.flavor.value == "full" and result.status.value != "available":
                        print(f"  - {name}: {result.status.value} - {result.details}")
                return 1
            else:
                print("\n[OK] Full 能力检查通过")

        return 0

    # --self-test: Run self-test
    if args.self_test == "offline-replay":
        return await run_offline_replay_test_async()

    # --doctor: Run diagnostics
    if args.doctor:
        return run_doctor()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Debug window mode
    if args.debug_window:
        return debug_windows(
            platform=args.platform,
            filter_pattern=args.window_filter,
            use_regex=args.window_regex,
        )

    # 加载 config.yaml，CLI > env > yaml > 默认值
    cfg = load_config(args.config)
    llm_cfg = cfg.get("llm", {}) if isinstance(cfg.get("llm"), dict) else {}

    provider = args.llm_provider or os.getenv("LLM_PROVIDER") or llm_cfg.get("provider", "none")
    model = args.llm_model or os.getenv("LLM_MODEL") or llm_cfg.get("model") or None
    timeout = args.llm_timeout or float(llm_cfg.get("timeout", 30.0))
    retries = (
        args.llm_retries if args.llm_retries is not None else int(llm_cfg.get("max_retries", 2))
    )
    budget = (
        args.llm_budget
        if args.llm_budget is not None
        else int(llm_cfg.get("budget_per_session", 50))
    )
    enable_log = args.llm_log or llm_cfg.get("enable_logging", False)
    max_actions_per_min = args.max_actions_per_min if args.max_actions_per_min is not None else None
    max_clicks = args.max_clicks if args.max_clicks is not None else None
    session_timeout = args.timeout if args.timeout is not None else None

    if not args.dry_run:
        if max_actions_per_min is None:
            max_actions_per_min = 30
        if max_clicks is None:
            max_clicks = 300
        if session_timeout is None:
            session_timeout = 300.0
        if provider != "none" and budget <= 0:
            logger.error("live 模式要求启用 LLM 预算，当前 --llm-budget=%s", budget)
            return 1

    # 创建平台适配器
    try:
        adapter = create_platform_adapter(args.platform)
    except Exception as e:
        logger.error(f"创建平台适配器失败: {e}")
        return 1

    # 创建 LLM 客户端
    llm_client = create_llm_client(
        provider=provider,
        model=model,
        timeout=timeout,
        max_retries=retries,
        budget=budget,
        enable_logging=enable_log,
    )

    # 启动摘要（不含敏感信息）
    logger.info(
        (
            "启动摘要: provider=%s model=%s llm_timeout=%.1f budget=%d dry_run=%s ui=%s "
            "max_actions_per_min=%s max_clicks=%s session_timeout=%s log_file=%s"
        ),
        provider,
        model or "(default)",
        timeout,
        budget,
        args.dry_run,
        args.ui,
        max_actions_per_min,
        max_clicks,
        session_timeout,
        args.log_file,
    )

    # 能力探测摘要
    if not args.debug_window:
        print(format_capability_summary())

    # TUI 模式
    if args.ui == "tui":
        return run_tui(
            adapter=adapter,
            llm_client=llm_client,
            dry_run=args.dry_run,
            interval=args.interval,
            budget=budget,
            max_actions_per_min=max_actions_per_min,
            max_clicks=max_clicks,
            timeout=session_timeout,
        )

    assistant = JinchanchanAssistant(
        platform_adapter=adapter,
        llm_client=llm_client,
        decision_interval=args.interval,
        dry_run=args.dry_run,
        max_actions_per_min=max_actions_per_min,
        max_clicks=max_clicks,
        timeout=session_timeout,
        llm_budget=budget,
    )

    await assistant.run()
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

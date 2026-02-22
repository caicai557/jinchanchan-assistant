"""
金铲铲助手 - 主程序入口

AI 驱动的金铲铲之战游戏助手，支持 Mac PlayCover 和 Windows 模拟器
"""

import argparse
import asyncio
import logging
import os
import platform
import sys
from pathlib import Path
from typing import Any, TypedDict

import yaml

# 版本号
__version__ = "0.1.0"

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from core.action import ActionType
from core.action_queue import ActionQueue
from core.control.action_executor import ActionExecutor
from core.game_state import GameState
from core.llm.client import LLMClient, LLMConfig, LLMProvider
from core.protocols import PlatformAdapter
from core.rules.decision_engine import DecisionEngineBuilder


def get_capability_summary() -> dict[str, Any]:
    """
    获取能力探测摘要（不触发重依赖导入）

    Returns:
        能力摘要字典
    """
    capabilities: dict[str, Any] = {}

    # OCR 可用性（不实际导入 onnxruntime）
    try:
        import rapidocr_onnxruntime  # noqa: F401

        capabilities["ocr"] = "rapidocr"
    except ImportError:
        try:
            import pytesseract  # noqa: F401

            capabilities["ocr"] = "tesseract"
        except ImportError:
            capabilities["ocr"] = "unavailable"

    # 模板匹配（OpenCV）
    try:
        import cv2  # noqa: F401

        capabilities["template_matching"] = "opencv"
    except ImportError:
        capabilities["template_matching"] = "unavailable"

    # LLM providers（只检查环境变量，不导入）
    llm_available: list[str] = []
    if os.getenv("ANTHROPIC_API_KEY"):
        llm_available.append("anthropic")
    if os.getenv("OPENAI_API_KEY"):
        llm_available.append("openai")
    if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
        llm_available.append("gemini")
    capabilities["llm_configured"] = llm_available

    # 模板数量
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

    # 平台适配器可用性
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
    """格式化能力摘要为可读字符串"""
    from core.capabilities import get_capability_matrix

    matrix = get_capability_matrix()
    cap = get_capability_summary()

    lines = [
        f"=== 金铲铲助手 v{__version__} [{matrix.flavor.value.upper()}] ===",
        f"平台: {cap['platform']} | Python: {cap['python']}",
        "",
        matrix.format_summary(),
    ]

    return "\n".join(lines)


class TUIState(TypedDict):
    """TUI 状态"""

    last_screenshot: Any  # PIL.Image.Image | None
    last_action: str
    last_source: str
    last_confidence: float
    action_queue: ActionQueue


# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("jinchanchan")


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
    ):
        self.adapter = platform_adapter
        self.llm_client = llm_client
        self.decision_interval = decision_interval
        self.dry_run = dry_run

        # 初始化决策引擎
        engine_builder = DecisionEngineBuilder()
        if llm_client:
            engine_builder.with_llm(llm_client)
        self.decision_engine = engine_builder.build()

        # 初始化动作执行器
        self.executor = ActionExecutor(self.adapter)

        # 状态
        self._running = False
        self._game_state = GameState()

        # 统计
        self._stats = {
            "total_decisions": 0,
            "actions_executed": 0,
            "errors": 0,
        }

    async def run(self) -> None:
        """运行助手"""
        logger.info("金铲铲助手启动")
        self._running = True

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

    async def _game_loop(self) -> None:
        """游戏主循环"""
        try:
            # 1. 获取游戏截图
            screenshot = self.adapter.get_screenshot()
            logger.debug("获取截图成功")

            # 2. 决策
            result = await self.decision_engine.decide(
                screenshot=screenshot, game_state=self._game_state, priority="balanced"
            )

            self._stats["total_decisions"] += 1
            logger.info(
                f"决策结果: {result.action.type.value} "
                f"(来源: {result.source}, 置信度: {result.confidence:.2f})"
            )

            # 3. 执行动作
            if result.action.type != ActionType.NONE:
                if self.dry_run:
                    logger.info(f"[dry-run] 跳过执行: {result.action.type.value}")
                else:
                    exec_result = await self.executor.execute(result.action)

                    if exec_result.success:
                        self._stats["actions_executed"] += 1
                        logger.info(f"执行成功: {result.action.type.value}")
                    else:
                        logger.warning(f"执行失败: {exec_result.error}")

                    await asyncio.sleep(0.5)

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
        width, height = screenshot.size
        extracted = {}

        # 分析顶部区域
        top_region = screenshot.crop((0, 0, width, 60))
        top_pixels = list(top_region.getdata())

        # 检测金币
        gold_pixels = sum(1 for p in top_pixels if p[1] > 200 and p[2] < 100)
        extracted["gold"] = min(gold_pixels // 100, 100)

        # 分析商店区域
        shop_region = screenshot.crop((40, 900, 1880, 1060))
        shop_pixels = list(shop_region.getdata())

        slot_colors = [
            (80, 160, 80),
            (80, 80, 160),
            (160, 80, 160),
            (160, 120, 80),
            (200, 160, 80),
        ]

        detected_slots = 0
        for color in slot_colors:
            close_pixels = sum(
                1
                for p in shop_pixels
                if abs(p[0] - color[0]) < 30
                and abs(p[1] - color[1]) < 30
                and abs(p[2] - color[2]) < 30
            )
            if close_pixels > 100:
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
) -> int:
    """
    运行 TUI 界面

    Args:
        adapter: 平台适配器
        llm_client: LLM 客户端
        dry_run: 是否只读模式
        interval: 决策间隔
        budget: LLM 预算

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
            # 获取截图
            screenshot = adapter.get_screenshot()
            state["last_screenshot"] = screenshot

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
    parser = argparse.ArgumentParser(description="金铲铲助手")
    parser.add_argument(
        "--version", "-V", action="store_true", default=False, help="显示版本和能力摘要"
    )
    parser.add_argument(
        "--capabilities", action="store_true", default=False, help="显示能力探测摘要并退出"
    )
    parser.add_argument(
        "--require-full",
        action="store_true",
        default=False,
        help="要求 Full flavor，缺失能力时返回非零退出码",
    )
    parser.add_argument(
        "--self-test",
        choices=["offline-replay"],
        default=None,
        help="运行自检测试并生成 replay_results.json",
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
    parser.add_argument("--interval", "-i", type=float, default=2.0)
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument(
        "--debug-window",
        action="store_true",
        default=False,
        help="枚举并输出所有候选窗口（仅 mac）",
    )
    parser.add_argument(
        "--window-filter",
        default=None,
        help="窗口过滤模式（contains 或 regex 配合 --window-regex）",
    )
    parser.add_argument(
        "--window-regex",
        action="store_true",
        default=False,
        help="使用正则匹配窗口过滤",
    )
    parser.add_argument(
        "--ui",
        choices=["none", "tui"],
        default="none",
        help="UI 模式 (default: none)",
    )

    args = parser.parse_args()

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

    # --self-test: 运行自检
    if args.self_test == "offline-replay":
        return await run_offline_replay_test_async()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # 窗口调试模式
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
        "启动摘要: provider=%s model=%s timeout=%.1f budget=%d dry_run=%s ui=%s",
        provider,
        model or "(default)",
        timeout,
        budget,
        args.dry_run,
        args.ui,
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
        )

    assistant = JinchanchanAssistant(
        platform_adapter=adapter,
        llm_client=llm_client,
        decision_interval=args.interval,
        dry_run=args.dry_run,
    )

    await assistant.run()
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

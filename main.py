"""
金铲铲助手 - 主程序入口

AI 驱动的金铲铲之战游戏助手，支持 Mac PlayCover 和 Windows 模拟器
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

import yaml

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from core.action import ActionType
from core.control.action_executor import ActionExecutor
from core.game_state import GameState
from core.llm.client import LLMClient, LLMConfig, LLMProvider
from core.protocols import PlatformAdapter
from core.rules.decision_engine import DecisionEngineBuilder

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
        from rich.live import Live
        from rich.panel import Panel
        from rich.table import Table
    except ImportError:
        print("TUI 需要 rich 库: pip install rich")
        return 1

    console = Console()
    assistant = JinchanchanAssistant(
        platform_adapter=adapter,
        llm_client=llm_client,
        decision_interval=interval,
        dry_run=dry_run,
    )

    def build_ui() -> Panel:
        """构建 TUI 界面"""
        stats = assistant._stats
        engine_stats = assistant.decision_engine.get_stats()
        llm_calls = llm_client._call_count if llm_client else 0

        table = Table(show_header=False, box=None)
        table.add_column("key", style="cyan")
        table.add_column("value", style="green")

        table.add_row("模式", "[red]DRY-RUN[/red]" if dry_run else "[green]LIVE[/green]")
        table.add_row("决策次数", str(stats["total_decisions"]))
        table.add_row("动作执行", str(stats["actions_executed"]))
        table.add_row("错误计数", str(stats["errors"]))
        table.add_row("规则决策", str(engine_stats.get("rule_decisions", 0)))
        table.add_row("LLM 决策", str(engine_stats.get("llm_decisions", 0)))
        table.add_row("LLM 调用", f"{llm_calls}/{budget}")

        window_info = adapter.get_window_info()
        if window_info:
            table.add_row("窗口", f"{window_info.width}x{window_info.height}")
        else:
            table.add_row("窗口", "[red]未找到[/red]")

        return Panel(table, title="金铲铲助手", border_style="blue")

    async def run_with_ui() -> None:
        """带 UI 的运行循环"""
        console.print("[bold green]启动 TUI 模式，按 Ctrl+C 退出[/bold green]")
        console.print(f"[cyan]dry_run={dry_run} budget={budget}[/cyan]")

        # 简化版：每秒刷新一次 UI
        import asyncio

        assistant._running = True
        try:
            while assistant._running:
                with Live(build_ui(), console=console, refresh_per_second=1):
                    await assistant._game_loop()
                    await asyncio.sleep(interval)
        except KeyboardInterrupt:
            assistant._running = False
            assistant._print_stats()

    asyncio.run(run_with_ui())
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(description="金铲铲助手")

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

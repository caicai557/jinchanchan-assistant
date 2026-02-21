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
        auto_start: bool = False,
    ):
        """
        初始化助手

        Args:
            platform_adapter: 平台适配器
            llm_client: LLM 客户端（可选）
            decision_interval: 决策间隔（秒）
            auto_start: 是否自动开始
        """
        self.adapter = platform_adapter
        self.llm_client = llm_client
        self.decision_interval = decision_interval

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
                exec_result = await self.executor.execute(result.action)

                if exec_result.success:
                    self._stats["actions_executed"] += 1
                    logger.info(f"执行成功: {result.action.type.value}")
                else:
                    logger.warning(f"执行失败: {exec_result.error}")

                # 执行后短暂等待
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
    provider: str, api_key: str | None = None, model: str | None = None
) -> LLMClient | None:
    """
    创建 LLM 客户端

    Args:
        provider: 提供商名称
        api_key: API Key
        model: 模型名称

    Returns:
        LLMClient 实例或 None
    """
    if provider == "none":
        return None

    try:
        provider_enum = LLMProvider(provider)
        default_model = LLMConfig.DEFAULT_MODELS.get(provider_enum, "")
        final_model = model or default_model or ""

        return LLMClient(
            LLMConfig(
                provider=provider_enum,
                api_key=api_key or os.getenv(f"{provider.upper()}_API_KEY"),
                model=final_model,
            )
        )
    except Exception as e:
        logger.warning(f"创建 LLM 客户端失败: {e}")
        return None


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="金铲铲助手 - AI 驱动的金铲铲之战游戏助手")

    # 平台选项
    parser.add_argument(
        "--platform",
        "-p",
        choices=["mac", "windows"],
        default="mac",
        help="运行平台 (default: mac)",
    )

    # LLM 选项
    parser.add_argument(
        "--llm-provider",
        choices=["anthropic", "openai", "qwen", "none"],
        default="none",
        help="LLM 提供商 (default: none)",
    )
    parser.add_argument("--llm-model", help="LLM 模型名称")
    parser.add_argument("--llm-api-key", help="LLM API Key (也可以通过环境变量设置)")

    # 运行选项
    parser.add_argument(
        "--interval", "-i", type=float, default=2.0, help="决策间隔秒数 (default: 2.0)"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")

    args = parser.parse_args()

    # 配置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # 创建平台适配器
    try:
        adapter = create_platform_adapter(args.platform)
        logger.info(f"平台适配器创建成功: {args.platform}")
    except Exception as e:
        logger.error(f"创建平台适配器失败: {e}")
        return 1

    # 创建 LLM 客户端
    llm_client = create_llm_client(
        provider=args.llm_provider, api_key=args.llm_api_key, model=args.llm_model
    )

    if llm_client:
        logger.info(f"LLM 客户端创建成功: {args.llm_provider}")
    else:
        logger.info("使用纯规则模式（无 LLM）")

    # 创建并运行助手
    assistant = JinchanchanAssistant(
        platform_adapter=adapter, llm_client=llm_client, decision_interval=args.interval
    )

    await assistant.run()

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

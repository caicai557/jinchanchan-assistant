"""
动作执行器

将决策引擎的动作转换为实际的游戏操作
"""

import asyncio
import random
import time
from dataclasses import dataclass
from typing import Any

from core.action import Action, ActionType
from core.coordinate_scaler import CoordinateScaler, Resolution
from core.protocols import PlatformAdapter


@dataclass
class ExecutionResult:
    """执行结果"""

    success: bool
    action: Action
    error: str | None = None
    latency_ms: int = 0


class ActionExecutor:
    """
    动作执行器

    将抽象动作转换为具体的平台操作
    """

    # 参考分辨率 (1920x1080) 下的坐标配置
    _REFERENCE_COORDS: dict[str, Any] = {
        # 商店槽位 (5个) — 与 GameRegions 对齐
        "shop_slots": [(380, 1000), (670, 1000), (960, 1000), (1250, 1000), (1540, 1000)],
        # 刷新按钮
        "refresh_button": (200, 1000),
        # 购买经验按钮
        "level_up_button": (200, 930),
        # 棋盘位置 (4行7列，左上角)
        "board_origin": (200, 400),
        "board_cell_size": (80, 80),
        # 备战席 (9个槽位)
        "bench_slots": [(200 + i * 80, 820) for i in range(9)],
    }

    def __init__(
        self,
        adapter: PlatformAdapter,
        click_delay: float = 0.1,
        humanize: bool = True,
        random_delay_range: tuple[float, float] = (0.05, 0.2),
        resolution: Resolution | None = None,
    ):
        """
        初始化执行器

        Args:
            adapter: 平台适配器
            click_delay: 点击延迟
            humanize: 是否添加拟人化延迟
            random_delay_range: 随机延迟范围
            resolution: 目标分辨率，None 时自动检测
        """
        self.adapter = adapter
        self.click_delay = click_delay
        self.humanize = humanize
        self.random_delay_range = random_delay_range

        # 坐标缩放器
        self._scaler = CoordinateScaler(resolution)
        self._coord_config = self._scale_coords(self._scaler)

        # 执行统计
        self._stats = {
            "total_actions": 0,
            "successful_actions": 0,
            "failed_actions": 0,
        }

    def _scale_coords(self, scaler: CoordinateScaler) -> dict[str, Any]:
        """根据缩放器计算目标分辨率的坐标"""
        return {
            "shop_slots": scaler.scale_points(self._REFERENCE_COORDS["shop_slots"]),
            "refresh_button": scaler.scale_point(*self._REFERENCE_COORDS["refresh_button"]),
            "level_up_button": scaler.scale_point(*self._REFERENCE_COORDS["level_up_button"]),
            "board_origin": scaler.scale_point(*self._REFERENCE_COORDS["board_origin"]),
            "board_cell_size": scaler.scale_size(*self._REFERENCE_COORDS["board_cell_size"]),
            "bench_slots": scaler.scale_points(self._REFERENCE_COORDS["bench_slots"]),
        }

    def update_resolution(self, width: int, height: int) -> None:
        """
        更新目标分辨率并重新计算坐标

        Args:
            width: 窗口宽度
            height: 窗口高度
        """
        self._scaler = CoordinateScaler.from_window_size(width, height)
        self._coord_config = self._scale_coords(self._scaler)

    def auto_detect_resolution(self) -> tuple[int, int]:
        """
        自动检测窗口分辨率并更新坐标

        Returns:
            检测到的 (width, height)
        """
        window_info = self.adapter.get_window_info()
        if window_info:
            self.update_resolution(window_info.width, window_info.height)
            return (window_info.width, window_info.height)
        return (1920, 1080)

    async def execute(self, action: Action) -> ExecutionResult:
        """
        执行动作

        Args:
            action: 要执行的动作

        Returns:
            ExecutionResult
        """
        start_time = time.time()
        self._stats["total_actions"] += 1

        # 添加拟人化延迟
        if self.humanize:
            await self._random_delay()

        try:
            result = await self._execute_action(action)

            latency = int((time.time() - start_time) * 1000)

            if result.success:
                self._stats["successful_actions"] += 1
            else:
                self._stats["failed_actions"] += 1

            result.latency_ms = latency
            return result

        except Exception as e:
            self._stats["failed_actions"] += 1
            return ExecutionResult(
                success=False,
                action=action,
                error=str(e),
                latency_ms=int((time.time() - start_time) * 1000),
            )

    async def _execute_action(self, action: Action) -> ExecutionResult:
        """执行具体动作"""
        handlers = {
            ActionType.BUY_HERO: self._execute_buy_hero,
            ActionType.SELL_HERO: self._execute_sell_hero,
            ActionType.MOVE_HERO: self._execute_move_hero,
            ActionType.REFRESH_SHOP: self._execute_refresh_shop,
            ActionType.LEVEL_UP: self._execute_level_up,
            ActionType.EQUIP_ITEM: self._execute_equip_item,
            ActionType.WAIT: self._execute_wait,
            ActionType.NONE: self._execute_none,
        }

        handler = handlers.get(action.type)
        if handler is None:
            return ExecutionResult(
                success=False, action=action, error=f"未知的动作类型: {action.type}"
            )

        return await handler(action)

    async def _execute_buy_hero(self, action: Action) -> ExecutionResult:
        """执行购买英雄"""
        if action.position is None:
            return ExecutionResult(success=False, action=action, error="购买动作缺少槽位信息")

        slot_index = action.position[0] if isinstance(action.position, tuple) else action.position

        if not (0 <= slot_index < 5):
            return ExecutionResult(
                success=False, action=action, error=f"无效的槽位索引: {slot_index}"
            )

        # 获取商店槽位坐标并转换为屏幕坐标
        shop_coords = self._coord_config["shop_slots"][slot_index]
        # shop_coords 是 tuple[int, int]
        sx, sy = shop_coords[0], shop_coords[1]
        screen_x, screen_y = self.adapter.window_to_screen(sx, sy)

        # 添加随机偏移
        screen_x += random.randint(-10, 10)
        screen_y += random.randint(-5, 5)

        # 执行点击
        success = self.adapter.click(screen_x, screen_y)

        return ExecutionResult(
            success=success, action=action, error=None if success else "点击失败"
        )

    async def _execute_sell_hero(self, action: Action) -> ExecutionResult:
        """执行出售英雄"""
        # 出售通常需要右键点击或拖动到特定区域
        # 这里简化为右键点击备战席位置

        if action.position is None:
            return ExecutionResult(success=False, action=action, error="出售动作缺少位置信息")

        # 假设 position 是备战席索引
        bench_index = action.position[0] if isinstance(action.position, tuple) else action.position

        if not (0 <= bench_index < 9):
            return ExecutionResult(
                success=False, action=action, error=f"无效的备战席索引: {bench_index}"
            )

        bench_coords = self._coord_config["bench_slots"][bench_index]
        bx, by = bench_coords[0], bench_coords[1]
        screen_x, screen_y = self.adapter.window_to_screen(bx, by)

        # 右键点击出售
        success = self.adapter.click(screen_x, screen_y, button="right")

        return ExecutionResult(
            success=success, action=action, error=None if success else "出售点击失败"
        )

    async def _execute_move_hero(self, action: Action) -> ExecutionResult:
        """执行移动英雄"""
        if action.source_position is None or action.position is None:
            return ExecutionResult(success=False, action=action, error="移动动作缺少位置信息")

        # 获取源位置坐标
        source = self._get_hero_position_coords(action.source_position)
        if source is None:
            return ExecutionResult(
                success=False, action=action, error=f"无效的源位置: {action.source_position}"
            )

        # 获取目标位置坐标
        target = self._get_hero_position_coords(action.position)
        if target is None:
            return ExecutionResult(
                success=False, action=action, error=f"无效的目标位置: {action.position}"
            )

        # 转换为屏幕坐标
        source_screen = self.adapter.window_to_screen(*source)
        target_screen = self.adapter.window_to_screen(*target)

        # 执行拖动
        success = self.adapter.drag(
            source_screen[0], source_screen[1], target_screen[0], target_screen[1], duration=0.3
        )

        return ExecutionResult(
            success=success, action=action, error=None if success else "拖动失败"
        )

    async def _execute_refresh_shop(self, action: Action) -> ExecutionResult:
        """执行刷新商店"""
        refresh_coords = self._coord_config["refresh_button"]
        rx, ry = refresh_coords[0], refresh_coords[1]
        screen_x, screen_y = self.adapter.window_to_screen(rx, ry)

        screen_x += random.randint(-10, 10)
        screen_y += random.randint(-5, 5)

        success = self.adapter.click(screen_x, screen_y)

        return ExecutionResult(
            success=success, action=action, error=None if success else "刷新点击失败"
        )

    async def _execute_level_up(self, action: Action) -> ExecutionResult:
        """执行升级"""
        level_up_coords = self._coord_config["level_up_button"]
        lx, ly = level_up_coords[0], level_up_coords[1]
        screen_x, screen_y = self.adapter.window_to_screen(lx, ly)

        screen_x += random.randint(-10, 10)
        screen_y += random.randint(-5, 5)

        success = self.adapter.click(screen_x, screen_y)

        return ExecutionResult(
            success=success, action=action, error=None if success else "升级点击失败"
        )

    async def _execute_equip_item(self, action: Action) -> ExecutionResult:
        """执行装备"""
        # 装备操作需要先点击装备，再点击英雄
        # 这里简化处理，实际需要更复杂的逻辑
        return ExecutionResult(success=False, action=action, error="装备操作暂未实现")

    async def _execute_wait(self, action: Action) -> ExecutionResult:
        """执行等待"""
        duration = action.metadata.get("duration", 1.0)
        await asyncio.sleep(duration)

        return ExecutionResult(success=True, action=action)

    async def _execute_none(self, action: Action) -> ExecutionResult:
        """执行无操作"""
        return ExecutionResult(success=True, action=action)

    def _get_hero_position_coords(self, position: tuple[int, ...]) -> tuple[int, int] | None:
        """
        获取英雄位置的窗口坐标

        Args:
            position: (row, col) 或 (bench_index, -1)

        Returns:
            (x, y) 窗口坐标或 None
        """
        if len(position) < 2:
            return None

        row: int = position[0]
        col: int = position[1]

        # 备战席
        if col == -1:
            if not (0 <= row < 9):
                return None
            bench_slot = self._coord_config["bench_slots"][row]
            return (int(bench_slot[0]), int(bench_slot[1]))

        # 棋盘
        if not (0 <= row < 4 and 0 <= col < 7):
            return None

        origin = self._coord_config["board_origin"]
        cell_size = self._coord_config["board_cell_size"]

        x = int(origin[0]) + col * int(cell_size[0]) + int(cell_size[0]) // 2
        y = int(origin[1]) + row * int(cell_size[1]) + int(cell_size[1]) // 2

        return (x, y)

    async def _random_delay(self) -> None:
        """添加随机延迟"""
        delay = random.uniform(*self.random_delay_range)
        await asyncio.sleep(delay)

    def update_coord_config(self, config: dict[str, Any]) -> None:
        """更新坐标配置"""
        self._coord_config.update(config)

    def get_stats(self) -> dict[str, int]:
        """获取执行统计"""
        return self._stats.copy()

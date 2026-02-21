"""
UI 区域定义

定义 1920x1080 参考分辨率下的游戏 UI 区域，运行时通过 CoordinateScaler 缩放
"""

from dataclasses import dataclass

from core.coordinate_scaler import CoordinateScaler


@dataclass(frozen=True)
class UIRegion:
    """UI 区域（不可变）"""

    name: str
    x: int
    y: int
    width: int
    height: int

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        """获取边界框 (x1, y1, x2, y2)"""
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    @property
    def center(self) -> tuple[int, int]:
        """获取中心点"""
        return (self.x + self.width // 2, self.y + self.height // 2)

    def scale(self, scaler: CoordinateScaler) -> "UIRegion":
        """缩放到目标分辨率"""
        sx, sy, sw, sh = scaler.scale_rect(self.x, self.y, self.width, self.height)
        return UIRegion(name=self.name, x=sx, y=sy, width=sw, height=sh)


class GameRegions:
    """
    游戏 UI 区域定义

    所有坐标基于 1920x1080 参考分辨率
    """

    # === 商店区域 ===
    # 商店位于屏幕底部，5 个槽位
    SHOP_BASE = UIRegion(
        name="shop_base",
        x=240,  # 左边距
        y=940,  # 底部区域
        width=1440,  # 5 个槽位总宽度
        height=120,  # 槽位高度
    )

    # 单个商店槽位尺寸
    SHOP_SLOT_WIDTH = 280
    SHOP_SLOT_HEIGHT = 120
    SHOP_SLOT_GAP = 10  # 槽位间距

    @classmethod
    def shop_slot(cls, index: int) -> UIRegion:
        """
        获取指定商店槽位区域

        Args:
            index: 槽位索引 (0-4)

        Returns:
            UIRegion
        """
        if not 0 <= index <= 4:
            raise ValueError(f"商店槽位索引必须在 0-4 之间，当前: {index}")

        x = cls.SHOP_BASE.x + index * (cls.SHOP_SLOT_WIDTH + cls.SHOP_SLOT_GAP)
        return UIRegion(
            name=f"shop_slot_{index}",
            x=x,
            y=cls.SHOP_BASE.y,
            width=cls.SHOP_SLOT_WIDTH,
            height=cls.SHOP_SLOT_HEIGHT,
        )

    @classmethod
    def all_shop_slots(cls) -> list[UIRegion]:
        """获取所有商店槽位"""
        return [cls.shop_slot(i) for i in range(5)]

    # === 棋盘区域 ===
    # 4 行 x 7 列格子
    BOARD = UIRegion(
        name="board",
        x=240,  # 左边距
        y=200,  # 顶部
        width=1120,  # 7 列
        height=640,  # 4 行
    )

    # 单个格子尺寸
    CELL_WIDTH = 160
    CELL_HEIGHT = 160

    @classmethod
    def board_cell(cls, row: int, col: int) -> UIRegion:
        """
        获取棋盘格子区域

        Args:
            row: 行 (0-3, 从上到下)
            col: 列 (0-6, 从左到右)

        Returns:
            UIRegion
        """
        if not 0 <= row <= 3:
            raise ValueError(f"行索引必须在 0-3 之间，当前: {row}")
        if not 0 <= col <= 6:
            raise ValueError(f"列索引必须在 0-6 之间，当前: {col}")

        return UIRegion(
            name=f"board_cell_{row}_{col}",
            x=cls.BOARD.x + col * cls.CELL_WIDTH,
            y=cls.BOARD.y + row * cls.CELL_HEIGHT,
            width=cls.CELL_WIDTH,
            height=cls.CELL_HEIGHT,
        )

    @classmethod
    def all_board_cells(cls) -> list[UIRegion]:
        """获取所有棋盘格子"""
        return [cls.board_cell(row, col) for row in range(4) for col in range(7)]

    # === 羁绊徽章区域 ===
    # 位于屏幕左侧
    SYNERGY_BADGES = UIRegion(
        name="synergy_badges",
        x=0,
        y=200,
        width=200,
        height=600,
    )

    # 单个羁绊徽章尺寸
    SYNERGY_BADGE_WIDTH = 180
    SYNERGY_BADGE_HEIGHT = 60
    SYNERGY_BADGE_GAP = 5

    @classmethod
    def synergy_badge(cls, index: int) -> UIRegion:
        """
        获取羁绊徽章区域

        Args:
            index: 徽章索引 (0-9)

        Returns:
            UIRegion
        """
        if not 0 <= index <= 9:
            raise ValueError(f"羁绊徽章索引必须在 0-9 之间，当前: {index}")

        return UIRegion(
            name=f"synergy_badge_{index}",
            x=cls.SYNERGY_BADGES.x + 10,
            y=cls.SYNERGY_BADGES.y + index * (cls.SYNERGY_BADGE_HEIGHT + cls.SYNERGY_BADGE_GAP),
            width=cls.SYNERGY_BADGE_WIDTH,
            height=cls.SYNERGY_BADGE_HEIGHT,
        )

    # === 装备栏区域 ===
    ITEM_INVENTORY = UIRegion(
        name="item_inventory",
        x=1520,
        y=200,
        width=200,
        height=400,
    )

    # 单个装备格子尺寸
    ITEM_SLOT_WIDTH = 50
    ITEM_SLOT_HEIGHT = 50
    ITEM_SLOT_GAP = 5

    @classmethod
    def item_slot(cls, index: int) -> UIRegion:
        """
        获取装备槽位区域

        Args:
            index: 槽位索引 (0-9)

        Returns:
            UIRegion
        """
        if not 0 <= index <= 9:
            raise ValueError(f"装备槽位索引必须在 0-9 之间，当前: {index}")

        col = index % 4
        row = index // 4

        return UIRegion(
            name=f"item_slot_{index}",
            x=cls.ITEM_INVENTORY.x + 10 + col * (cls.ITEM_SLOT_WIDTH + cls.ITEM_SLOT_GAP),
            y=cls.ITEM_INVENTORY.y + 10 + row * (cls.ITEM_SLOT_HEIGHT + cls.ITEM_SLOT_GAP),
            width=cls.ITEM_SLOT_WIDTH,
            height=cls.ITEM_SLOT_HEIGHT,
        )

    # === 备战席区域 ===
    BENCH = UIRegion(
        name="bench",
        x=240,
        y=850,
        width=1120,
        height=80,
    )

    # 单个备战席格子
    BENCH_SLOT_WIDTH = 120
    BENCH_SLOT_HEIGHT = 80
    BENCH_SLOT_GAP = 5

    @classmethod
    def bench_slot(cls, index: int) -> UIRegion:
        """
        获取备战席槽位区域

        Args:
            index: 槽位索引 (0-8)

        Returns:
            UIRegion
        """
        if not 0 <= index <= 8:
            raise ValueError(f"备战席槽位索引必须在 0-8 之间，当前: {index}")

        return UIRegion(
            name=f"bench_slot_{index}",
            x=cls.BENCH.x + index * (cls.BENCH_SLOT_WIDTH + cls.BENCH_SLOT_GAP),
            y=cls.BENCH.y,
            width=cls.BENCH_SLOT_WIDTH,
            height=cls.BENCH_SLOT_HEIGHT,
        )

    @classmethod
    def all_bench_slots(cls) -> list[UIRegion]:
        """获取所有备战席槽位"""
        return [cls.bench_slot(i) for i in range(9)]

    # === 玩家信息区域 ===
    PLAYER_INFO = UIRegion(
        name="player_info",
        x=1720,
        y=0,
        width=200,
        height=100,
    )

    # 金币显示区域
    GOLD_DISPLAY = UIRegion(
        name="gold_display",
        x=1740,
        y=20,
        width=80,
        height=30,
    )

    # 等级显示区域
    LEVEL_DISPLAY = UIRegion(
        name="level_display",
        x=1740,
        y=55,
        width=80,
        height=30,
    )


def scale_regions(regions: list[UIRegion], scaler: CoordinateScaler) -> list[UIRegion]:
    """
    批量缩放区域

    Args:
        regions: UI 区域列表
        scaler: 坐标缩放器

    Returns:
        缩放后的区域列表
    """
    return [region.scale(scaler) for region in regions]

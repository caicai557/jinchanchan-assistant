"""
游戏状态定义
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GamePhase(str, Enum):
    """游戏阶段"""

    LOADING = "loading"  # 加载中
    PREPARATION = "preparation"  # 备战阶段
    COMBAT = "combat"  # 战斗阶段
    CAROUSEL = "carousel"  # 选秀阶段
    SETTLEMENT = "settlement"  # 结算阶段
    UNKNOWN = "unknown"  # 未知


class Hero(BaseModel):
    """英雄信息"""

    name: str = Field(..., description="英雄名称")
    cost: int = Field(..., ge=1, le=5, description="费用 1-5")
    stars: int = Field(default=1, ge=1, le=3, description="星级 1-3")
    level: int = Field(default=1, ge=1, description="等级")
    synergies: list[str] = Field(default_factory=list, description="羁绊列表")
    position: tuple[int, int] | None = Field(default=None, description="棋盘位置 (row, col)")
    items: list[str] = Field(default_factory=list, description="装备列表")

    model_config = ConfigDict(frozen=False)


class Synergy(BaseModel):
    """羁绊状态"""

    name: str = Field(..., description="羁绊名称")
    count: int = Field(default=0, description="当前数量")
    breakpoints: list[int] = Field(default_factory=list, description="突破点")
    is_active: bool = Field(default=False, description="是否激活")
    next_breakpoint: int | None = Field(default=None, description="下一突破点")


@dataclass
class ShopSlot:
    """商店槽位"""

    index: int  # 槽位索引 0-4
    hero_name: str | None = None  # 英雄名称（None 表示空槽）
    cost: int = 0  # 费用
    is_sold: bool = False  # 是否已售出


@dataclass
class GameState:
    """
    完整的游戏状态

    包含所有游戏内信息，用于决策引擎分析
    """

    # 基础信息
    phase: GamePhase = GamePhase.UNKNOWN
    round_number: int = 0  # 当前回合数
    stage: int = 0  # 阶段 (1-6)

    # 玩家资源
    gold: int = 0  # 金币
    hp: int = 100  # 血量
    level: int = 1  # 等级
    exp: int = 0  # 经验值
    exp_to_level: int = 0  # 升级所需经验

    # 英雄相关
    heroes: list[Hero] = field(default_factory=list)  # 场上英雄
    bench_heroes: list[Hero] = field(default_factory=list)  # 备战席英雄
    synergies: dict[str, Synergy] = field(default_factory=dict)  # 羁绊状态

    # 商店
    shop_slots: list[ShopSlot] = field(default_factory=lambda: [ShopSlot(i) for i in range(5)])
    shop_locked: bool = False  # 商店是否锁定
    can_refresh: bool = True  # 是否可以刷新

    # 装备
    available_items: list[str] = field(default_factory=list)  # 可用装备

    # 对手信息（可选）
    opponents_hp: dict[str, int] = field(default_factory=dict)  # 对手血量

    # 元数据
    timestamp: float = 0.0  # 状态时间戳
    confidence: float = 1.0  # 状态识别置信度

    def get_hero_count(self, hero_name: str) -> int:
        """获取指定英雄的数量（场上+备战席）"""
        count = 0
        for hero in self.heroes:
            if hero.name == hero_name:
                count += 1
        for hero in self.bench_heroes:
            if hero.name == hero_name:
                count += 1
        return count

    def get_total_hero_count(self) -> int:
        """获取场上英雄总数"""
        return len(self.heroes)

    def get_max_hero_count(self) -> int:
        """获取最大可上场英雄数"""
        return self.level

    def can_add_hero(self) -> bool:
        """是否可以添加英雄到场上"""
        return self.get_total_hero_count() < self.get_max_hero_count()

    def get_bench_slots_used(self) -> int:
        """获取备战席已用槽位"""
        return len(self.bench_heroes)

    def has_bench_space(self) -> bool:
        """备战席是否有空位"""
        return len(self.bench_heroes) < 9

    def get_synergy_progress(self, synergy_name: str) -> Synergy | None:
        """获取指定羁绊的进度"""
        return self.synergies.get(synergy_name)

    def get_active_synergies(self) -> list[str]:
        """获取所有激活的羁绊"""
        return [name for name, s in self.synergies.items() if s.is_active]

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（用于 LLM 上下文）"""
        return {
            "phase": self.phase.value,
            "round": f"{self.stage}-{self.round_number}",
            "gold": self.gold,
            "hp": self.hp,
            "level": self.level,
            "exp": f"{self.exp}/{self.exp_to_level}",
            "heroes_on_board": [h.name for h in self.heroes],
            "heroes_on_bench": [h.name for h in self.bench_heroes],
            "active_synergies": self.get_active_synergies(),
            "shop": [
                {"slot": s.index, "hero": s.hero_name, "cost": s.cost} for s in self.shop_slots
            ],
        }

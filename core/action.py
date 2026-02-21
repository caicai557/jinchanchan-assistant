"""
游戏动作定义
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """动作类型"""

    # 英雄操作
    BUY_HERO = "buy_hero"  # 购买英雄
    SELL_HERO = "sell_hero"  # 出售英雄
    MOVE_HERO = "move_hero"  # 移动英雄

    # 商店操作
    REFRESH_SHOP = "refresh_shop"  # 刷新商店
    LOCK_SHOP = "lock_shop"  # 锁定/解锁商店

    # 等级操作
    LEVEL_UP = "level_up"  # 购买经验升级

    # 装备操作
    EQUIP_ITEM = "equip_item"  # 装备给英雄
    UNEQUIP_ITEM = "unequip_item"  # 卸下装备
    COMBINE_ITEMS = "combine_items"  # 合成装备

    # 战术操作
    DEPLOY_HERO = "deploy_hero"  # 从备战席部署英雄到场上
    RECALL_HERO = "recall_hero"  # 从场上收回英雄到备战席

    # 元操作
    WAIT = "wait"  # 等待
    NONE = "none"  # 无操作


class ActionPriority(int, Enum):
    """动作优先级"""

    CRITICAL = 100  # 关键操作（如保血）
    HIGH = 75  # 高优先级
    NORMAL = 50  # 正常优先级
    LOW = 25  # 低优先级
    BACKGROUND = 0  # 后台操作


@dataclass
class Action:
    """
    游戏动作

    表示一个可执行的游戏操作
    """

    type: ActionType
    target: str | None = None  # 目标（英雄名/装备名等）
    position: tuple[int, ...] | None = None  # 位置坐标 (x, y) 或 (slot_index,) 等
    source_position: tuple[int, ...] | None = None  # 源位置（用于移动操作）
    priority: ActionPriority = ActionPriority.NORMAL
    reasoning: str = ""  # 决策原因
    confidence: float = 1.0  # 动作置信度
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type.value,
            "target": self.target,
            "position": self.position,
            "source_position": self.source_position,
            "priority": self.priority.value,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
        }

    @classmethod
    def buy_hero(cls, hero_name: str, slot_index: int, reasoning: str = "") -> "Action":
        """创建购买英雄动作"""
        return cls(
            type=ActionType.BUY_HERO,
            target=hero_name,
            position=(slot_index,),
            reasoning=reasoning,
            priority=ActionPriority.HIGH,
        )

    @classmethod
    def sell_hero(cls, hero_name: str, position: tuple[int, int], reasoning: str = "") -> "Action":
        """创建出售英雄动作"""
        return cls(
            type=ActionType.SELL_HERO,
            target=hero_name,
            position=position,
            reasoning=reasoning,
            priority=ActionPriority.LOW,
        )

    @classmethod
    def move_hero(
        cls, hero_name: str, from_pos: tuple[int, int], to_pos: tuple[int, int], reasoning: str = ""
    ) -> "Action":
        """创建移动英雄动作"""
        return cls(
            type=ActionType.MOVE_HERO,
            target=hero_name,
            source_position=from_pos,
            position=to_pos,
            reasoning=reasoning,
            priority=ActionPriority.NORMAL,
        )

    @classmethod
    def refresh_shop(cls, reasoning: str = "") -> "Action":
        """创建刷新商店动作"""
        return cls(
            type=ActionType.REFRESH_SHOP,
            reasoning=reasoning,
            priority=ActionPriority.NORMAL,
        )

    @classmethod
    def level_up(cls, reasoning: str = "") -> "Action":
        """创建升级动作"""
        return cls(
            type=ActionType.LEVEL_UP,
            reasoning=reasoning,
            priority=ActionPriority.HIGH,
        )

    @classmethod
    def wait(cls, duration: float = 1.0, reasoning: str = "") -> "Action":
        """创建等待动作"""
        return cls(
            type=ActionType.WAIT,
            metadata={"duration": duration},
            reasoning=reasoning,
            priority=ActionPriority.BACKGROUND,
        )

    @classmethod
    def none_action(cls, reasoning: str = "") -> "Action":
        """创建无操作"""
        return cls(
            type=ActionType.NONE,
            reasoning=reasoning,
            priority=ActionPriority.BACKGROUND,
        )


class LLMActionResponse(BaseModel):
    """LLM 返回的动作响应"""

    # 分析结果
    analysis: str = Field(..., description="当前局势分析")

    # 识别的游戏状态
    detected_gold: int | None = Field(default=None, description="识别到的金币")
    detected_level: int | None = Field(default=None, description="识别到的等级")
    detected_hp: int | None = Field(default=None, description="识别到的血量")

    # 动作
    action_type: str = Field(..., description="动作类型")
    action_target: str | None = Field(default=None, description="动作目标")
    action_position: list[int] | None = Field(default=None, description="动作位置")
    action_source_position: list[int] | None = Field(default=None, description="源位置")

    # 推理
    reasoning: str = Field(default="", description="决策推理过程")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="置信度")

    def to_action(self) -> Action:
        """转换为 Action 对象"""
        action_type = ActionType(self.action_type)

        position = None
        if self.action_position:
            position = tuple(self.action_position)

        source_position = None
        if self.action_source_position:
            source_position = tuple(self.action_source_position)

        # 根据动作类型设置优先级
        priority = ActionPriority.NORMAL
        if action_type in [ActionType.BUY_HERO, ActionType.LEVEL_UP]:
            priority = ActionPriority.HIGH
        elif action_type in [ActionType.SELL_HERO, ActionType.REFRESH_SHOP]:
            priority = ActionPriority.NORMAL
        elif action_type in [ActionType.WAIT, ActionType.NONE]:
            priority = ActionPriority.LOW

        return Action(
            type=action_type,
            target=self.action_target,
            position=position,
            source_position=source_position,
            priority=priority,
            reasoning=self.reasoning,
            confidence=self.confidence,
        )


class ActionBatch(BaseModel):
    """动作批次（一次决策可能产生多个动作）"""

    actions: list[Action] = Field(default_factory=list, description="动作列表")
    reasoning: str = Field(default="", description="整体决策推理")
    timestamp: float = Field(default=0.0, description="决策时间戳")

    def add_action(self, action: Action) -> None:
        """添加动作"""
        self.actions.append(action)

    def sort_by_priority(self) -> list[Action]:
        """按优先级排序"""
        return sorted(self.actions, key=lambda a: a.priority.value, reverse=True)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "actions": [a.to_dict() for a in self.actions],
            "reasoning": self.reasoning,
            "timestamp": self.timestamp,
        }

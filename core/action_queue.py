"""
动作队列

管理待执行和已执行的动作
"""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from core.action import Action, ActionType


@dataclass
class QueuedAction:
    """队列中的动作"""

    action: Action
    queued_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending, executing, completed, failed
    error: str | None = None


class ActionQueue:
    """
    动作队列

    管理待执行和已执行的动作，支持优先级排序
    """

    def __init__(self, max_history: int = 100):
        """
        初始化动作队列

        Args:
            max_history: 最大历史记录数
        """
        self._pending: list[QueuedAction] = []
        self._history: deque[QueuedAction] = deque(maxlen=max_history)
        self._current: QueuedAction | None = None

    def enqueue(self, action: Action) -> QueuedAction:
        """
        将动作加入队列

        Args:
            action: 要执行的动作

        Returns:
            QueuedAction
        """
        queued = QueuedAction(action=action)
        self._pending.append(queued)
        # 按优先级排序
        self._pending.sort(key=lambda qa: qa.action.priority.value, reverse=True)
        return queued

    def enqueue_batch(self, actions: list[Action]) -> list[QueuedAction]:
        """
        批量加入队列

        Args:
            actions: 动作列表

        Returns:
            QueuedAction 列表
        """
        return [self.enqueue(a) for a in actions]

    def dequeue(self) -> QueuedAction | None:
        """
        取出下一个待执行动作

        Returns:
            QueuedAction 或 None
        """
        if not self._pending:
            return None

        queued = self._pending.pop(0)
        queued.status = "executing"
        self._current = queued
        return queued

    def complete_current(self, success: bool = True, error: str | None = None) -> None:
        """
        标记当前动作为完成

        Args:
            success: 是否成功
            error: 错误信息
        """
        if self._current:
            self._current.status = "completed" if success else "failed"
            self._current.error = error
            self._history.append(self._current)
            self._current = None

    def peek(self) -> QueuedAction | None:
        """
        查看下一个待执行动作（不移除）

        Returns:
            QueuedAction 或 None
        """
        return self._pending[0] if self._pending else None

    def clear_pending(self) -> int:
        """
        清空待执行队列

        Returns:
            清除的动作数
        """
        count = len(self._pending)
        self._pending.clear()
        return count

    def get_pending(self) -> list[QueuedAction]:
        """获取所有待执行动作"""
        return list(self._pending)

    def get_history(self, limit: int = 10) -> list[QueuedAction]:
        """
        获取历史记录

        Args:
            limit: 最大数量

        Returns:
            QueuedAction 列表（最新在前）
        """
        history = list(self._history)
        history.reverse()
        return history[:limit]

    def get_current(self) -> QueuedAction | None:
        """获取当前正在执行的动作"""
        return self._current

    def get_stats(self) -> dict[str, Any]:
        """获取队列统计"""
        completed = sum(1 for qa in self._history if qa.status == "completed")
        failed = sum(1 for qa in self._history if qa.status == "failed")

        return {
            "pending_count": len(self._pending),
            "history_count": len(self._history),
            "completed_count": completed,
            "failed_count": failed,
            "has_current": self._current is not None,
        }

    def format_pending(self, max_items: int = 5) -> str:
        """
        格式化待执行队列用于显示

        Args:
            max_items: 最大显示数量

        Returns:
            格式化字符串
        """
        if not self._pending:
            return "[dim]队列为空[/dim]"

        lines = []
        for i, qa in enumerate(self._pending[:max_items]):
            action = qa.action
            icon = self._get_action_icon(action.type)
            target = f" → {action.target}" if action.target else ""
            lines.append(f"  {icon} {action.type.value}{target}")

        if len(self._pending) > max_items:
            lines.append(f"  ... 还有 {len(self._pending) - max_items} 个")

        return "\n".join(lines)

    def format_history(self, max_items: int = 5) -> str:
        """
        格式化历史记录用于显示

        Args:
            max_items: 最大显示数量

        Returns:
            格式化字符串
        """
        if not self._history:
            return "[dim]暂无历史[/dim]"

        lines = []
        history = list(self._history)
        history.reverse()

        for qa in history[:max_items]:
            action = qa.action
            icon = "✓" if qa.status == "completed" else "✗"
            color = "green" if qa.status == "completed" else "red"
            lines.append(f"  [{color}]{icon}[/{color}] {action.type.value}")

        return "\n".join(lines)

    @staticmethod
    def _get_action_icon(action_type: ActionType) -> str:
        """获取动作图标"""
        icons = {
            ActionType.BUY_HERO: "🛒",
            ActionType.SELL_HERO: "💰",
            ActionType.MOVE_HERO: "↔️",
            ActionType.REFRESH_SHOP: "🔄",
            ActionType.LEVEL_UP: "⬆️",
            ActionType.EQUIP_ITEM: "⚔️",
            ActionType.WAIT: "⏳",
            ActionType.NONE: "—",
        }
        return icons.get(action_type, "•")

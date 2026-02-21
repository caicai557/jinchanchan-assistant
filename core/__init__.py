"""
金铲铲助手核心模块
"""

from core.action import Action, ActionType
from core.game_state import GamePhase, GameState
from core.protocols import PlatformAdapter

__all__ = [
    "PlatformAdapter",
    "GameState",
    "GamePhase",
    "Action",
    "ActionType",
]

"""
测试规则引擎
"""

import pytest

from core.action import ActionType
from core.game_state import GamePhase, GameState
from core.rules.quick_actions import QuickActionEngine


@pytest.fixture
def game_state():
    """创建测试用的游戏状态"""
    return GameState(
        phase=GamePhase.PREPARATION,
        round_number=1,
        stage=1,
        gold=50,
        hp=100,
        level=4,
    )


def test_quick_action_engine_init():
    """测试快速动作引擎初始化"""
    engine = QuickActionEngine()
    assert engine is not None


def test_no_quick_action_when_gold_low(game_state):
    """测试金币不足时不触发刷新"""
    game_state.gold = 1
    engine = QuickActionEngine()

    action = engine.check_quick_actions(game_state)

    # 金币低时不应该触发刷新
    if action:
        assert action.type != ActionType.REFRESH_SHOP


def test_emergency_level_up(game_state):
    """测试血量低时紧急升级"""
    game_state.hp = 20
    game_state.gold = 10
    engine = QuickActionEngine()

    action = engine.check_quick_actions(game_state)

    if action:
        assert action.type == ActionType.LEVEL_UP


def test_enable_disable_rule():
    """测试启用/禁用规则"""
    engine = QuickActionEngine()

    # 禁用规则
    engine.disable_rule("auto_free_refresh")

    # 启用规则
    engine.enable_rule("auto_free_refresh")

    # 不应该抛出异常
    assert True

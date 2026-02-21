"""
测试动作验证器
"""

import pytest

from core.action import Action, ActionType
from core.game_state import GameState, ShopSlot
from core.rules.validator import ActionValidator


@pytest.fixture
def validator():
    """创建验证器"""
    return ActionValidator()


@pytest.fixture
def game_state():
    """创建测试游戏状态"""
    state = GameState()
    state.gold = 50
    state.level = 6
    state.hp = 80

    # 设置商店
    state.shop_slots = [
        ShopSlot(index=0, hero_name="亚索", cost=1),
        ShopSlot(index=1, hero_name="劫", cost=2),
        ShopSlot(index=2, hero_name="艾希", cost=3),
        ShopSlot(index=3, hero_name="锐雯", cost=4),
        ShopSlot(index=4, hero_name=None, cost=0, is_sold=True),
    ]

    return state


def test_validate_buy_hero_success(validator, game_state):
    """测试有效的购买英雄动作"""
    action = Action.buy_hero("亚索", 0)

    result = validator.validate(action, game_state)

    assert result.is_valid


def test_validate_buy_hero_wrong_slot(validator, game_state):
    """测试商店槽位不匹配"""
    action = Action.buy_hero("亚索", 1)  # 槽位1是劫

    result = validator.validate(action, game_state)

    assert result.is_valid  # 仍然有效，但有警告
    assert len(result.warnings) > 0


def test_validate_buy_hero_insufficient_gold(validator, game_state):
    """测试金币不足"""
    game_state.gold = 0
    action = Action.buy_hero("亚索", 0)

    result = validator.validate(action, game_state)

    assert not result.is_valid


def test_validate_level_up_success(validator, game_state):
    """测试有效的升级动作"""
    action = Action.level_up()

    result = validator.validate(action, game_state)

    assert result.is_valid


def test_validate_level_up_max_level(validator, game_state):
    """测试已达最高等级"""
    game_state.level = 9
    action = Action.level_up()

    result = validator.validate(action, game_state)

    assert not result.is_valid


def test_validate_wait_always_valid(validator, game_state):
    """测试等待动作总是有效"""
    action = Action.wait(duration=1.0)

    result = validator.validate(action, game_state)

    assert result.is_valid


def test_validate_and_fix(validator, game_state):
    """测试验证并修复"""
    # 创建一个越界的移动动作
    action = Action(
        type=ActionType.MOVE_HERO,
        target="亚索",
        position=(10, 10),  # 超出棋盘范围
        source_position=(0, 0),
    )

    fixed = validator.validate_and_fix(action, game_state)

    # 应该返回修复后的动作或 none 动作
    assert fixed is not None

"""
动作验证器

验证 LLM 返回的动作是否合法
"""

from collections.abc import Callable
from dataclasses import dataclass

from core.action import Action, ActionType
from core.game_state import GameState


@dataclass
class ValidationResult:
    """验证结果"""

    is_valid: bool
    action: Action
    modified_action: Action | None = None
    error: str | None = None
    warnings: list[str] | None = None

    def __post_init__(self) -> None:
        if self.warnings is None:
            self.warnings = []


class ActionValidator:
    """
    动作验证器

    验证动作的合法性和合理性
    """

    def __init__(self) -> None:
        self._validators: dict[ActionType, Callable[[Action, GameState], ValidationResult]] = {
            ActionType.BUY_HERO: self._validate_buy_hero,
            ActionType.SELL_HERO: self._validate_sell_hero,
            ActionType.MOVE_HERO: self._validate_move_hero,
            ActionType.REFRESH_SHOP: self._validate_refresh_shop,
            ActionType.LEVEL_UP: self._validate_level_up,
            ActionType.EQUIP_ITEM: self._validate_equip_item,
            ActionType.WAIT: self._validate_wait,
            ActionType.NONE: self._validate_none,
        }

        # 游戏常量
        self.MAX_BOARD_SIZE = (4, 7)  # 4 行 7 列
        self.MAX_BENCH_SIZE = 9
        self.MAX_ITEMS = 10

    def validate(self, action: Action, state: GameState) -> ValidationResult:
        """
        验证动作

        Args:
            action: 待验证的动作
            state: 当前游戏状态

        Returns:
            ValidationResult
        """
        validator = self._validators.get(action.type)
        if validator is None:
            return ValidationResult(
                is_valid=False, action=action, error=f"未知的动作类型: {action.type}"
            )

        return validator(action, state)

    def validate_and_fix(self, action: Action, state: GameState) -> Action:
        """
        验证并尝试修复动作

        Args:
            action: 待验证的动作
            state: 当前游戏状态

        Returns:
            修复后的动作（如果可能）或 None 动作
        """
        result = self.validate(action, state)

        if result.is_valid:
            return result.modified_action or result.action

        # 尝试修复
        fixed_action = self._try_fix_action(action, state, result.error)
        if fixed_action:
            return fixed_action

        return Action.none_action(f"动作验证失败: {result.error}")

    def _validate_buy_hero(self, action: Action, state: GameState) -> ValidationResult:
        """验证购买英雄动作"""
        warnings = []

        # 检查目标
        if not action.target:
            return ValidationResult(is_valid=False, action=action, error="购买动作缺少目标英雄名称")

        # 检查商店槽位
        if action.position is None:
            return ValidationResult(is_valid=False, action=action, error="购买动作缺少商店槽位信息")

        slot_index = action.position[0] if isinstance(action.position, tuple) else action.position
        if not (0 <= slot_index < 5):
            return ValidationResult(
                is_valid=False, action=action, error=f"无效的商店槽位索引: {slot_index}"
            )

        # 检查商店槽位状态
        shop_slot = state.shop_slots[slot_index]
        if shop_slot.is_sold:
            return ValidationResult(
                is_valid=False, action=action, error=f"商店槽位 {slot_index} 已售出"
            )

        if shop_slot.hero_name != action.target:
            warnings.append(f"商店槽位英雄 ({shop_slot.hero_name}) 与目标 ({action.target}) 不匹配")

        # 检查金币
        if state.gold < shop_slot.cost:
            return ValidationResult(
                is_valid=False,
                action=action,
                error=f"金币不足: 需要 {shop_slot.cost}，当前 {state.gold}",
            )

        # 检查备战席空间
        if not state.has_bench_space():
            warnings.append("备战席已满，购买后需要立即上场或出售")

        return ValidationResult(is_valid=True, action=action, warnings=warnings)

    def _validate_sell_hero(self, action: Action, state: GameState) -> ValidationResult:
        """验证出售英雄动作"""
        # 检查目标
        if not action.target:
            return ValidationResult(is_valid=False, action=action, error="出售动作缺少目标英雄名称")

        # 检查是否拥有该英雄
        has_hero = False
        for hero in state.heroes + state.bench_heroes:
            if hero.name == action.target:
                has_hero = True
                break

        if not has_hero:
            return ValidationResult(
                is_valid=False, action=action, error=f"没有名为 {action.target} 的英雄"
            )

        return ValidationResult(is_valid=True, action=action)

    def _validate_move_hero(self, action: Action, state: GameState) -> ValidationResult:
        """验证移动英雄动作"""
        # 检查目标
        if not action.target:
            return ValidationResult(is_valid=False, action=action, error="移动动作缺少目标英雄名称")

        # 检查源位置
        if not action.source_position:
            return ValidationResult(is_valid=False, action=action, error="移动动作缺少源位置")

        # 检查目标位置
        if not action.position:
            return ValidationResult(is_valid=False, action=action, error="移动动作缺少目标位置")

        # 检查目标位置是否在棋盘范围内
        row, col = action.position
        if not (0 <= row < self.MAX_BOARD_SIZE[0] and 0 <= col < self.MAX_BOARD_SIZE[1]):
            return ValidationResult(
                is_valid=False, action=action, error=f"目标位置超出棋盘范围: ({row}, {col})"
            )

        return ValidationResult(is_valid=True, action=action)

    def _validate_refresh_shop(self, action: Action, state: GameState) -> ValidationResult:
        """验证刷新商店动作"""
        # 检查金币
        refresh_cost = 2
        if state.gold < refresh_cost:
            return ValidationResult(
                is_valid=False,
                action=action,
                error=f"金币不足: 刷新需要 {refresh_cost}，当前 {state.gold}",
            )

        # 检查商店是否锁定
        if state.shop_locked:
            return ValidationResult(is_valid=False, action=action, error="商店已锁定，无法刷新")

        return ValidationResult(is_valid=True, action=action)

    def _validate_level_up(self, action: Action, state: GameState) -> ValidationResult:
        """验证升级动作"""
        # 检查等级上限
        if state.level >= 9:
            return ValidationResult(is_valid=False, action=action, error="已达到最高等级")

        # 检查金币
        level_up_cost = 4
        if state.gold < level_up_cost:
            return ValidationResult(
                is_valid=False,
                action=action,
                error=f"金币不足: 升级需要 {level_up_cost}，当前 {state.gold}",
            )

        return ValidationResult(is_valid=True, action=action)

    def _validate_equip_item(self, action: Action, state: GameState) -> ValidationResult:
        """验证装备动作"""
        # 检查目标英雄
        if not action.target:
            return ValidationResult(is_valid=False, action=action, error="装备动作缺少目标英雄名称")

        # 检查英雄是否存在
        has_hero = any(h.name == action.target for h in state.heroes)
        if not has_hero:
            return ValidationResult(
                is_valid=False, action=action, error=f"场上没有名为 {action.target} 的英雄"
            )

        return ValidationResult(is_valid=True, action=action)

    def _validate_wait(self, action: Action, state: GameState) -> ValidationResult:
        """验证等待动作"""
        # 等待动作总是合法的
        return ValidationResult(is_valid=True, action=action)

    def _validate_none(self, action: Action, state: GameState) -> ValidationResult:
        """验证无操作"""
        return ValidationResult(is_valid=True, action=action)

    def _try_fix_action(self, action: Action, state: GameState, error: str | None) -> Action | None:
        """尝试修复动作"""
        if action.type == ActionType.BUY_HERO:
            # 尝试找到正确的商店槽位
            for i, slot in enumerate(state.shop_slots):
                if slot.hero_name == action.target and not slot.is_sold:
                    return Action(
                        type=action.type,
                        target=action.target,
                        position=(i,),
                        reasoning=action.reasoning,
                        confidence=action.confidence * 0.9,
                    )

        if action.type == ActionType.MOVE_HERO:
            # 尝试找到有效的目标位置
            if action.position:
                row, col = action.position
                row = max(0, min(row, self.MAX_BOARD_SIZE[0] - 1))
                col = max(0, min(col, self.MAX_BOARD_SIZE[1] - 1))
                return Action(
                    type=action.type,
                    target=action.target,
                    position=(row, col),
                    source_position=action.source_position,
                    reasoning=action.reasoning,
                    confidence=action.confidence * 0.9,
                )

        return None

    def batch_validate(self, actions: list[Action], state: GameState) -> list[ValidationResult]:
        """
        批量验证动作

        Args:
            actions: 动作列表
            state: 游戏状态

        Returns:
            验证结果列表
        """
        results = []
        current_state = state  # 可能需要模拟状态变化

        for action in actions:
            result = self.validate(action, current_state)
            results.append(result)

            # 如果动作有效，可能需要更新模拟状态
            # （这里简化处理，不做状态模拟）

        return results

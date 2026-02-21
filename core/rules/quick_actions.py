"""
快速动作引擎

处理低级、固定的游戏操作，无需 LLM 决策
"""

from collections.abc import Callable
from dataclasses import dataclass

from core.action import Action, ActionPriority
from core.game_state import GameState


@dataclass
class QuickActionRule:
    """快速动作规则"""

    name: str
    condition: Callable[[GameState], bool]
    action_factory: Callable[[GameState], Action]
    priority: ActionPriority = ActionPriority.HIGH
    description: str = ""


class QuickActionEngine:
    """
    快速动作引擎

    处理简单的、规则明确的操作，减轻 LLM 负担
    """

    def __init__(self):
        self._rules: list[QuickActionRule] = []
        self._enabled_rules: set = set()

        # 注册默认规则
        self._register_default_rules()

    def _register_default_rules(self):
        """注册默认的快速动作规则"""

        # 规则1：自动购买免费刷新（如果有）
        self.register_rule(
            QuickActionRule(
                name="auto_free_refresh",
                condition=lambda state: (
                    state.can_refresh and state.gold >= 2 and self._should_refresh(state)
                ),
                action_factory=lambda state: Action.refresh_shop("规则触发：需要刷新商店"),
                priority=ActionPriority.NORMAL,
                description="自动刷新商店",
            )
        )

        # 规则2：购买能合成三星的英雄
        self.register_rule(
            QuickActionRule(
                name="auto_buy_for_three_star",
                condition=lambda state: self._can_complete_three_star(state),
                action_factory=lambda state: self._create_buy_action_for_three_star(state),
                priority=ActionPriority.HIGH,
                description="购买能合成三星的英雄",
            )
        )

        # 规则3：血量低时升级保血
        self.register_rule(
            QuickActionRule(
                name="emergency_level_up",
                condition=lambda state: state.hp <= 30 and state.gold >= 4 and state.level < 9,
                action_factory=lambda state: Action.level_up("规则触发：血量低，紧急升级"),
                priority=ActionPriority.CRITICAL,
                description="血量低时紧急升级",
            )
        )

        # 规则4：有空位且商店有需要的英雄
        self.register_rule(
            QuickActionRule(
                name="auto_buy_needed_hero",
                condition=lambda state: (
                    state.can_add_hero()
                    and state.gold >= 1
                    and self._has_needed_hero_in_shop(state)
                ),
                action_factory=lambda state: self._create_buy_needed_hero_action(state),
                priority=ActionPriority.HIGH,
                description="自动购买需要的英雄",
            )
        )

        # 规则5：备战席满时自动出售多余英雄
        self.register_rule(
            QuickActionRule(
                name="auto_sell_extra_hero",
                condition=lambda state: (
                    not state.has_bench_space() and self._has_sellable_hero(state)
                ),
                action_factory=lambda state: self._create_sell_action(state),
                priority=ActionPriority.LOW,
                description="自动出售多余英雄",
            )
        )

        # 启用所有默认规则
        self._enabled_rules = {rule.name for rule in self._rules}

    def register_rule(self, rule: QuickActionRule) -> None:
        """注册规则"""
        self._rules.append(rule)

    def enable_rule(self, rule_name: str) -> None:
        """启用规则"""
        self._enabled_rules.add(rule_name)

    def disable_rule(self, rule_name: str) -> None:
        """禁用规则"""
        self._enabled_rules.discard(rule_name)

    def check_quick_actions(self, state: GameState) -> Action | None:
        """
        检查是否有快速动作可以执行

        Args:
            state: 当前游戏状态

        Returns:
            可执行的 Action 或 None
        """
        # 过滤启用的规则
        active_rules = [rule for rule in self._rules if rule.name in self._enabled_rules]

        # 按优先级排序
        active_rules.sort(key=lambda r: r.priority.value, reverse=True)

        # 检查每个规则
        for rule in active_rules:
            try:
                if rule.condition(state):
                    action = rule.action_factory(state)
                    action.metadata["rule_name"] = rule.name
                    return action
            except Exception as e:
                print(f"规则 {rule.name} 执行出错: {e}")
                continue

        return None

    def get_all_matching_rules(self, state: GameState) -> list[Action]:
        """
        获取所有匹配的规则（用于批量执行）

        Args:
            state: 当前游戏状态

        Returns:
            匹配的 Action 列表
        """
        actions = []

        for rule in self._rules:
            if rule.name not in self._enabled_rules:
                continue

            try:
                if rule.condition(state):
                    action = rule.action_factory(state)
                    action.metadata["rule_name"] = rule.name
                    actions.append(action)
            except Exception:
                continue

        # 按优先级排序
        actions.sort(key=lambda a: a.priority.value, reverse=True)
        return actions

    # ===== 辅助方法 =====

    def _should_refresh(self, state: GameState) -> bool:
        """判断是否应该刷新商店"""
        # 简单规则：金币充足且没有需要的英雄
        if state.gold < 4:
            return False

        # 检查商店是否有需要的英雄
        for slot in state.shop_slots:
            if slot.hero_name and not slot.is_sold:
                # 如果英雄是场上英雄的同类，不刷新
                for hero in state.heroes + state.bench_heroes:
                    if hero.name == slot.hero_name:
                        return False

        return True

    def _can_complete_three_star(self, state: GameState) -> bool:
        """检查是否能完成三星"""
        for slot in state.shop_slots:
            if slot.hero_name and not slot.is_sold:
                # 统计该英雄数量
                count = state.get_hero_count(slot.hero_name)
                # 如果已有2个，再买1个就能三星（1星英雄）
                if count == 2 and slot.cost <= 3:
                    return state.gold >= slot.cost
        return False

    def _create_buy_action_for_three_star(self, state: GameState) -> Action:
        """创建购买三星英雄的动作"""
        for i, slot in enumerate(state.shop_slots):
            if slot.hero_name and not slot.is_sold:
                count = state.get_hero_count(slot.hero_name)
                if count == 2 and slot.cost <= 3:
                    return Action.buy_hero(
                        hero_name=slot.hero_name,
                        slot_index=i,
                        reasoning=f"购买 {slot.hero_name} 完成三星",
                    )

        return Action.none_action("没有可购买的三星英雄")

    def _has_needed_hero_in_shop(self, state: GameState) -> bool:
        """检查商店是否有需要的英雄"""
        for slot in state.shop_slots:
            if slot.hero_name and not slot.is_sold:
                # 检查是否能增强现有羁绊
                # 这里简化处理，实际应该检查英雄的羁绊
                if slot.cost <= state.gold:
                    return True

        return False

    def _create_buy_needed_hero_action(self, state: GameState) -> Action:
        """创建购买需要英雄的动作"""
        for i, slot in enumerate(state.shop_slots):
            if slot.hero_name and not slot.is_sold and slot.cost <= state.gold:
                return Action.buy_hero(
                    hero_name=slot.hero_name,
                    slot_index=i,
                    reasoning=f"购买 {slot.hero_name} 增强阵容",
                )

        return Action.none_action("没有可购买的英雄")

    def _has_sellable_hero(self, state: GameState) -> bool:
        """检查是否有可出售的英雄"""
        # 检查备战席是否有重复英雄
        hero_counts: dict[str, int] = {}
        for hero in state.bench_heroes:
            hero_counts[hero.name] = hero_counts.get(hero.name, 0) + 1

        # 如果有单个的（不能合成的），可以出售
        for name, count in hero_counts.items():
            if count == 1:
                return True

        return False

    def _create_sell_action(self, state: GameState) -> Action:
        """创建出售英雄的动作"""
        hero_counts: dict[str, int] = {}
        for i, hero in enumerate(state.bench_heroes):
            hero_counts[hero.name] = hero_counts.get(hero.name, 0) + 1
            if hero_counts[hero.name] == 1:
                # 找到第一个单例英雄
                return Action.sell_hero(
                    hero_name=hero.name,
                    position=(i, -1),  # 备战席位置
                    reasoning=f"出售单例 {hero.name} 腾出空间",
                )

        return Action.none_action("没有可出售的英雄")

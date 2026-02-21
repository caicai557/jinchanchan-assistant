"""
游戏 Prompt 模板

为金铲铲之战设计的 LLM Prompt
"""

from typing import Any


class GamePrompts:
    """游戏 Prompt 模板"""

    # 系统提示词
    SYSTEM_PROMPT = """
你是一个金铲铲之战（Teamfight Tactics）的 AI 助手，负责分析游戏画面并做出最优决策。

## 你的能力
1. 识别屏幕上的英雄、装备、金币、血量、等级等信息
2. 根据当前阵容和局势推荐最佳操作
3. 输出结构化的动作指令（JSON 格式）

## 游戏知识（S13 福星版本）

### 羁绊
- **福星**：3/6 羁绊，胜利获得额外奖励
- **战神**：2/4/6/8 羁绊，提供攻击力和吸血
- **决斗大师**：2/4/6/8 羁绊，攻击提供攻速
- **神射手**：2/4 羁绊，攻击弹射
- **魔法师**：2/4/6/8 羁绊，双重施法
- **夜幽**：2/4/6/8 羁绊，提供法术强度
- **灵魂莲华**：2/4/6 羁绊，链接英雄
- **猩红之月**：3/6/9 羁绊，召唤加里奥
- **天神**：2/4/6/8 羁绊，飞升效果
- **宗师**：2/3/4 羁绊，降低敌人攻速

### 费用体系
- 1费英雄：商店概率 100%/75%/55%/45%/30%/20%/15%（等级 1-7）
- 2费英雄：商店概率随等级降低
- 3费英雄：3级解锁，4-6级概率最高
- 4费英雄：4级解锁，7-8级概率最高
- 5费英雄：5级解锁，8-9级概率最高

### 关键装备
- **输出装**：无尽之刃、最后的轻语、鬼索的狂暴之刃、卢安娜的飓风
- **法术装**：珠光护手、大天使之杖、灭世者的死亡之帽
- **防御装**：守护天使、石像鬼板甲、狂徒铠甲
- **辅助装**：基克的先驱、能量圣杯、钢铁烈阳之匣

### 经济原则
- 存钱到 50 金币吃满利息
- 合理使用连胜/连败奖励
- 关键回合（4-1、4-5、5-1）考虑梭哈

## 输出格式
你必须在回复末尾输出 JSON 格式的动作指令：
```json
{
  "analysis": "当前局势分析",
  "detected_gold": 50,
  "detected_level": 7,
  "detected_hp": 65,
  "action_type": "buy_hero",
  "action_target": "亚索",
  "action_position": [0],
  "reasoning": "购买亚索可以激活决斗大师羁绊",
  "confidence": 0.9
}
```

## 动作类型
- `buy_hero`: 购买英雄（action_position 为商店槽位索引 0-4）
- `sell_hero`: 出售英雄（action_position 为棋盘位置 [row, col]）
- `move_hero`: 移动英雄（action_source_position 和 action_position）
- `refresh_shop`: 刷新商店
- `level_up`: 购买经验升级
- `equip_item`: 装备给英雄
- `wait`: 等待（metadata.duration 为等待秒数）
- `none`: 无操作

## 注意事项
1. 优先保证生存（血量低于 30 考虑保血）
2. 合理规划经济（非必要不刷新）
3. 根据来牌灵活调整阵容
4. 注意观察对手阵容
"""

    # 分析游戏状态
    ANALYZE_GAME_STATE = """
请仔细分析这张金铲铲之战的游戏截图，识别并报告以下信息：

1. **游戏阶段**：当前是备战/战斗/选秀/结算阶段？
2. **回合数**：显示的回合数是多少（如 2-1、3-2 等）？
3. **金币数量**：当前有多少金币？
4. **血量**：当前血量是多少？
5. **等级**：当前等级是多少？经验值情况？
6. **商店内容**：商店里有哪 5 个英雄？分别是什么费用？
7. **场上英雄**：棋盘上有哪些英雄？它们的位置？
8. **备战席**：备战席上有哪些英雄？
9. **羁绊状态**：当前激活了哪些羁绊？
10. **装备**：有哪些可用的装备？

请以结构化的方式输出识别结果。
"""

    # 决策提示模板
    DECISION_PROMPT_TEMPLATE = """
## 当前游戏状态
{game_state_summary}

## 当前阶段
{phase}

## 决策优先级
{priority_instruction}

## 请做出决策
基于以上信息和游戏画面，请做出最优决策并输出 JSON 格式的动作指令。
"""

    # 优先级说明
    PRIORITY_INSTRUCTIONS = {
        "save_gold": """
当前策略：存钱
- 除非是关键英雄，否则不购买
- 不刷新商店
- 尽量存到 50 金币吃满利息
""",
        "level_up": """
当前策略：升人口
- 优先购买经验
- 目标是快速达到关键等级（7 级或 8 级）
- 可以适当刷新找关键英雄
""",
        "chase_three": """
当前策略：追三
- 优先购买已有的低费英雄
- 考虑刷新商店
- 目标是将核心英雄升到三星
""",
        "protect_hp": """
当前策略：保血
- 不惜代价提升战力
- 购买所有能上的英雄
- 考虑升级保血
""",
        "balanced": """
当前策略：平衡发展
- 正常运营
- 合理购买英雄
- 适度刷新
- 保持经济健康
""",
    }

    @classmethod
    def build_decision_prompt(cls, game_state: dict[str, Any], priority: str = "balanced") -> str:
        """
        构建决策提示

        Args:
            game_state: 游戏状态字典
            priority: 优先级

        Returns:
            完整的决策提示
        """
        # 构建状态摘要
        summary_parts = []

        if "gold" in game_state:
            summary_parts.append(f"金币：{game_state['gold']}")
        if "level" in game_state:
            summary_parts.append(f"等级：{game_state['level']}")
        if "hp" in game_state:
            summary_parts.append(f"血量：{game_state['hp']}")
        if "round" in game_state:
            summary_parts.append(f"回合：{game_state['round']}")
        if "heroes_on_board" in game_state:
            summary_parts.append(f"场上英雄：{', '.join(game_state['heroes_on_board'])}")
        if "heroes_on_bench" in game_state:
            summary_parts.append(f"备战席：{', '.join(game_state['heroes_on_bench'])}")
        if "active_synergies" in game_state:
            summary_parts.append(f"激活羁绊：{', '.join(game_state['active_synergies'])}")

        game_state_summary = "\n".join(summary_parts)

        # 获取优先级说明
        priority_instruction = cls.PRIORITY_INSTRUCTIONS.get(
            priority, cls.PRIORITY_INSTRUCTIONS["balanced"]
        )

        # 获取阶段
        phase = game_state.get("phase", "备战中")

        return cls.DECISION_PROMPT_TEMPLATE.format(
            game_state_summary=game_state_summary,
            phase=phase,
            priority_instruction=priority_instruction,
        )

    @classmethod
    def build_annotation_prompt(cls, annotation_description: str) -> str:
        """
        构建带标注的提示

        Args:
            annotation_description: 标注区域描述

        Returns:
            带标注说明的提示
        """
        return f"""
## 截图标注说明
图片上已标注了编号区域，方便你定位：

{annotation_description}

请参考这些标注区域进行识别和决策。
"""


class PromptBuilder:
    """Prompt 构建器"""

    def __init__(self, game_version: str = "S13"):
        self.game_version = game_version
        self._custom_knowledge: list[str] = []

    def add_custom_knowledge(self, knowledge: str) -> None:
        """添加自定义游戏知识"""
        self._custom_knowledge.append(knowledge)

    def build_system_prompt(self) -> str:
        """构建系统提示"""
        prompt = GamePrompts.SYSTEM_PROMPT

        if self._custom_knowledge:
            prompt += "\n\n## 补充知识\n" + "\n".join(self._custom_knowledge)

        return prompt

    def build_analysis_prompt(self, focus_areas: list[str] | None = None) -> str:
        """
        构建分析提示

        Args:
            focus_areas: 关注区域列表

        Returns:
            分析提示
        """
        prompt = GamePrompts.ANALYZE_GAME_STATE

        if focus_areas:
            prompt += "\n\n请特别关注以下区域：\n"
            for area in focus_areas:
                prompt += f"- {area}\n"

        return prompt

    def build_decision_prompt(
        self,
        game_state: dict[str, Any],
        priority: str = "balanced",
        include_annotation: bool = False,
        annotation_description: str | None = None,
    ) -> str:
        """
        构建完整决策提示

        Args:
            game_state: 游戏状态
            priority: 优先级
            include_annotation: 是否包含标注说明
            annotation_description: 标注描述

        Returns:
            完整决策提示
        """
        prompt = GamePrompts.build_decision_prompt(game_state, priority)

        if include_annotation and annotation_description:
            prompt = GamePrompts.build_annotation_prompt(annotation_description) + "\n" + prompt

        return prompt

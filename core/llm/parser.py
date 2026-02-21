"""
LLM 响应解析器

解析 LLM 返回的文本，提取结构化信息
"""

import json
import re
from dataclasses import dataclass
from typing import Any

from core.action import Action, ActionType, LLMActionResponse


@dataclass
class ParsedResponse:
    """解析后的响应"""

    raw_text: str
    analysis: str
    action: Action | None = None
    detected_state: dict[str, Any] | None = None
    error: str | None = None
    confidence: float = 1.0


class ResponseParser:
    """
    LLM 响应解析器

    支持多种格式的响应解析
    """

    def __init__(self):
        self._action_type_mapping = {
            "buy": ActionType.BUY_HERO,
            "购买": ActionType.BUY_HERO,
            "buy_hero": ActionType.BUY_HERO,
            "sell": ActionType.SELL_HERO,
            "出售": ActionType.SELL_HERO,
            "sell_hero": ActionType.SELL_HERO,
            "move": ActionType.MOVE_HERO,
            "移动": ActionType.MOVE_HERO,
            "move_hero": ActionType.MOVE_HERO,
            "refresh": ActionType.REFRESH_SHOP,
            "刷新": ActionType.REFRESH_SHOP,
            "refresh_shop": ActionType.REFRESH_SHOP,
            "level": ActionType.LEVEL_UP,
            "升级": ActionType.LEVEL_UP,
            "level_up": ActionType.LEVEL_UP,
            "equip": ActionType.EQUIP_ITEM,
            "装备": ActionType.EQUIP_ITEM,
            "equip_item": ActionType.EQUIP_ITEM,
            "wait": ActionType.WAIT,
            "等待": ActionType.WAIT,
            "none": ActionType.NONE,
            "无操作": ActionType.NONE,
        }

    def parse(self, response_text: str) -> ParsedResponse:
        """
        解析 LLM 响应

        Args:
            response_text: LLM 返回的文本

        Returns:
            ParsedResponse
        """
        # 提取 JSON 块
        json_match = self._extract_json(response_text)

        if json_match:
            try:
                json_data = json.loads(json_match)
                return self._parse_json_response(response_text, json_data)
            except json.JSONDecodeError:
                pass

        # 尝试解析非结构化响应
        return self._parse_unstructured_response(response_text)

    def _extract_json(self, text: str) -> str | None:
        """提取 JSON 块"""
        # 尝试匹配 ```json ... ``` 格式
        json_pattern = r"```json\s*([\s\S]*?)\s*```"
        match = re.search(json_pattern, text)
        if match:
            return match.group(1)

        # 尝试匹配 { ... } 格式
        brace_pattern = r"\{[\s\S]*\}"
        match = re.search(brace_pattern, text)
        if match:
            return match.group(0)

        return None

    def _parse_json_response(self, raw_text: str, json_data: dict[str, Any]) -> ParsedResponse:
        """解析 JSON 格式的响应"""
        try:
            # 提取分析文本
            analysis = json_data.get("analysis", "")

            # 提取检测到的状态
            detected_state = {}
            if "detected_gold" in json_data:
                detected_state["gold"] = json_data["detected_gold"]
            if "detected_level" in json_data:
                detected_state["level"] = json_data["detected_level"]
            if "detected_hp" in json_data:
                detected_state["hp"] = json_data["detected_hp"]

            # 提取动作
            action = None
            action_type_str = json_data.get("action_type", "none")

            if action_type_str and action_type_str != "none":
                try:
                    llm_response = LLMActionResponse(
                        analysis=analysis,
                        detected_gold=json_data.get("detected_gold"),
                        detected_level=json_data.get("detected_level"),
                        detected_hp=json_data.get("detected_hp"),
                        action_type=action_type_str,
                        action_target=json_data.get("action_target"),
                        action_position=json_data.get("action_position"),
                        action_source_position=json_data.get("action_source_position"),
                        reasoning=json_data.get("reasoning", ""),
                        confidence=json_data.get("confidence", 1.0),
                    )
                    action = llm_response.to_action()
                except Exception:
                    action = self._create_action_from_dict(json_data)

            return ParsedResponse(
                raw_text=raw_text,
                analysis=analysis,
                action=action,
                detected_state=detected_state if detected_state else None,
                confidence=json_data.get("confidence", 1.0),
            )

        except Exception as e:
            return ParsedResponse(
                raw_text=raw_text,
                analysis="",
                error=str(e),
            )

    def _parse_unstructured_response(self, text: str) -> ParsedResponse:
        """解析非结构化响应"""
        # 尝试提取动作关键词
        action = None
        analysis = text

        # 查找动作关键词
        for keyword, action_type in self._action_type_mapping.items():
            if keyword in text.lower():
                # 尝试提取目标
                target = self._extract_target(text, keyword)

                action = Action(
                    type=action_type,
                    target=target,
                    reasoning=text[:200],  # 使用前 200 字符作为推理
                )
                break

        return ParsedResponse(
            raw_text=text,
            analysis=analysis,
            action=action,
            confidence=0.5,  # 非结构化响应置信度较低
        )

    def _extract_target(self, text: str, keyword: str) -> str | None:
        """从文本中提取动作目标"""
        # 查找关键词后的内容
        pattern = rf'{keyword}["\s]+([^"，。\n]+)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def _create_action_from_dict(self, data: dict[str, Any]) -> Action | None:
        """从字典创建动作"""
        action_type_str = data.get("action_type", "none")
        action_type = self._action_type_mapping.get(action_type_str.lower(), ActionType.NONE)

        if action_type == ActionType.NONE:
            return None

        return Action(
            type=action_type,
            target=data.get("action_target"),
            position=(tuple(data["action_position"]) if data.get("action_position") else None),
            source_position=(
                tuple(data["action_source_position"])
                if data.get("action_source_position")
                else None
            ),
            reasoning=data.get("reasoning", ""),
            confidence=data.get("confidence", 1.0),
        )

    def parse_with_validation(
        self, response_text: str, expected_types: list[ActionType] | None = None
    ) -> ParsedResponse:
        """
        解析并验证响应

        Args:
            response_text: 响应文本
            expected_types: 期望的动作类型列表

        Returns:
            验证后的响应
        """
        parsed = self.parse(response_text)

        # 验证动作类型
        if parsed.action and expected_types:
            if parsed.action.type not in expected_types:
                parsed.error = f"意外的动作类型: {parsed.action.type}"
                parsed.confidence *= 0.5

        return parsed


def parse_llm_response(response_text: str) -> ParsedResponse:
    """解析 LLM 响应的便捷函数"""
    parser = ResponseParser()
    return parser.parse(response_text)

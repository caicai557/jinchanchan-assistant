"""
混合决策引擎

结合 LLM 和规则引擎，实现最优决策
"""

import time
from dataclasses import dataclass
from typing import Any

from PIL import Image

from core.action import Action, ActionType
from core.game_state import GameState
from core.llm.client import LLMClient
from core.llm.parser import ResponseParser
from core.llm.prompts import PromptBuilder
from core.rules.quick_actions import QuickActionEngine
from core.rules.validator import ActionValidator
from core.vision.som_annotator import SoMAnnotator


@dataclass
class DecisionResult:
    """决策结果"""

    action: Action
    source: str  # "rule" 或 "llm"
    llm_analysis: str | None = None
    confidence: float = 1.0
    latency_ms: int = 0


class HybridDecisionEngine:
    """
    混合决策引擎

    结合规则引擎和 LLM，实现高效且智能的决策
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        use_som_annotation: bool = True,
        llm_fallback: bool = True,
    ):
        """
        初始化决策引擎

        Args:
            llm_client: LLM 客户端
            use_som_annotation: 是否使用 SoM 标注
            llm_fallback: 规则失败时是否回退到 LLM
        """
        self.llm_client = llm_client
        self.use_som_annotation = use_som_annotation
        self.llm_fallback = llm_fallback

        # 初始化子组件
        self.quick_action_engine = QuickActionEngine()
        self.action_validator = ActionValidator()
        self.response_parser = ResponseParser()
        self.prompt_builder = PromptBuilder()
        self.som_annotator = SoMAnnotator()

        # 统计信息
        self._stats: dict[str, Any] = {
            "total_decisions": 0,
            "rule_decisions": 0,
            "llm_decisions": 0,
            "llm_errors": 0,
            "avg_latency_ms": 0.0,
        }

    async def decide(
        self,
        screenshot: Image.Image,
        game_state: GameState,
        priority: str = "balanced",
        force_llm: bool = False,
    ) -> DecisionResult:
        """
        做出决策

        Args:
            screenshot: 游戏截图
            game_state: 游戏状态
            priority: 决策优先级
            force_llm: 强制使用 LLM

        Returns:
            DecisionResult
        """
        start_time = time.time()
        self._stats["total_decisions"] += 1

        # 1. 检查快速动作（规则引擎）
        if not force_llm:
            quick_action = self.quick_action_engine.check_quick_actions(game_state)
            if quick_action:
                # 验证动作
                validated = self.action_validator.validate_and_fix(quick_action, game_state)
                if validated.type != ActionType.NONE:
                    latency = int((time.time() - start_time) * 1000)
                    self._stats["rule_decisions"] += 1
                    return DecisionResult(
                        action=validated, source="rule", confidence=1.0, latency_ms=latency
                    )

        # 2. LLM 决策
        if self.llm_client:
            result = await self._llm_decide(screenshot, game_state, priority)
            if result:
                latency = int((time.time() - start_time) * 1000)
                self._update_latency_stats(latency)
                return result

        # 3. 回退：返回等待动作
        latency = int((time.time() - start_time) * 1000)
        return DecisionResult(
            action=Action.wait(duration=1.0, reasoning="无可用决策"),
            source="fallback",
            confidence=0.0,
            latency_ms=latency,
        )

    async def _llm_decide(
        self, screenshot: Image.Image, game_state: GameState, priority: str
    ) -> DecisionResult | None:
        """使用 LLM 进行决策"""
        try:
            # 准备图片（可能添加标注）
            processed_image = screenshot
            annotation_description = None

            if self.use_som_annotation:
                annotated, regions = self.som_annotator.create_full_annotation(screenshot)
                processed_image = annotated
                annotation_description = self.som_annotator.regions_to_description(
                    [r for region_list in regions.values() for r in region_list]
                )

            # 构建 Prompt
            game_state_dict = game_state.to_dict()
            prompt = self.prompt_builder.build_decision_prompt(
                game_state=game_state_dict,
                priority=priority,
                include_annotation=self.use_som_annotation,
                annotation_description=annotation_description,
            )

            # 调用 LLM
            if self.llm_client is None:
                return None

            response = await self.llm_client.chat_with_image(
                prompt=prompt,
                image=processed_image,
                system_prompt=self.prompt_builder.build_system_prompt(),
            )

            # 解析响应
            parsed = self.response_parser.parse(response)

            if parsed.error:
                self._stats["llm_errors"] += 1
                return None

            # 验证动作
            if parsed.action:
                validated_action = self.action_validator.validate_and_fix(parsed.action, game_state)

                self._stats["llm_decisions"] += 1

                return DecisionResult(
                    action=validated_action,
                    source="llm",
                    llm_analysis=parsed.analysis,
                    confidence=parsed.confidence,
                )

            return None

        except Exception as e:
            self._stats["llm_errors"] += 1
            print(f"LLM 决策出错: {e}")
            return None

    async def analyze_state(self, screenshot: Image.Image) -> dict[str, Any]:
        """
        分析游戏状态（仅分析，不决策）

        Args:
            screenshot: 游戏截图

        Returns:
            状态分析结果
        """
        if not self.llm_client:
            return {}

        try:
            response = await self.llm_client.analyze_game_state(screenshot)
            parsed = self.response_parser.parse(response)

            return {
                "analysis": parsed.analysis,
                "detected_state": parsed.detected_state,
                "raw_response": parsed.raw_text,
            }

        except Exception as e:
            return {"error": str(e)}

    def enable_rule(self, rule_name: str) -> None:
        """启用规则"""
        self.quick_action_engine.enable_rule(rule_name)

    def disable_rule(self, rule_name: str) -> None:
        """禁用规则"""
        self.quick_action_engine.disable_rule(rule_name)

    def add_custom_rule(self, rule) -> None:
        """添加自定义规则"""
        self.quick_action_engine.register_rule(rule)

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return self._stats.copy()

    def _update_latency_stats(self, latency_ms: float) -> None:
        """更新延迟统计"""
        total = self._stats["total_decisions"]
        current_avg = self._stats["avg_latency_ms"]
        self._stats["avg_latency_ms"] = (current_avg * (total - 1) + latency_ms) / total


class DecisionEngineBuilder:
    """决策引擎构建器"""

    def __init__(self) -> None:
        self._llm_client: LLMClient | None = None
        self._use_som_annotation: bool = True
        self._llm_fallback: bool = True
        self._disabled_rules: list[str] = []

    def with_llm(self, client: LLMClient) -> "DecisionEngineBuilder":
        """设置 LLM 客户端"""
        self._llm_client = client
        return self

    def with_llm_provider(
        self, provider: str, api_key: str | None = None, model: str | None = None
    ) -> "DecisionEngineBuilder":
        """设置 LLM 提供商"""
        from core.llm.client import create_llm_client

        self._llm_client = create_llm_client(provider=provider, api_key=api_key, model=model)
        return self

    def with_som_annotation(self, enabled: bool = True) -> "DecisionEngineBuilder":
        """设置是否使用 SoM 标注"""
        self._use_som_annotation = enabled
        return self

    def with_llm_fallback(self, enabled: bool = True) -> "DecisionEngineBuilder":
        """设置是否使用 LLM 回退"""
        self._llm_fallback = enabled
        return self

    def disable_rule(self, rule_name: str) -> "DecisionEngineBuilder":
        """禁用规则"""
        self._disabled_rules.append(rule_name)
        return self

    def build(self) -> HybridDecisionEngine:
        """构建决策引擎"""
        engine = HybridDecisionEngine(
            llm_client=self._llm_client,
            use_som_annotation=self._use_som_annotation,
            llm_fallback=self._llm_fallback,
        )

        for rule_name in self._disabled_rules:
            engine.disable_rule(rule_name)

        return engine

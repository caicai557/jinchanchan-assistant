"""
Smoke E2E: decision_engine → action_executor 完整路径（无真实 LLM / 窗口）
"""

from __future__ import annotations

import pytest
from PIL import Image

from core.action import ActionType
from core.control.action_executor import ActionExecutor
from core.game_state import GamePhase, GameState
from core.protocols import WindowInfo
from core.rules.decision_engine import HybridDecisionEngine
from core.vision.som_annotator import SoMAnnotator

# ── FakePlatformAdapter ──────────────────────────────────────────────


class FakePlatformAdapter:
    """满足 PlatformAdapter 协议，记录所有调用。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self._window = WindowInfo(title="fake", left=0, top=0, width=1920, height=1080)

    # ── 截图 / 窗口 ──

    def get_screenshot(self) -> Image.Image:
        self.calls.append(("get_screenshot", ()))
        return Image.new("RGB", (1920, 1080))

    def get_game_window_rect(self) -> tuple[int, int, int, int]:
        return self._window.rect

    def get_window_info(self) -> WindowInfo:
        return self._window

    def is_game_active(self) -> bool:
        return True

    def activate_game(self) -> bool:
        return True

    # ── 输入 ──

    def click(
        self, x: int, y: int, button: str = "left", clicks: int = 1, interval: float = 0.1
    ) -> bool:
        self.calls.append(("click", (x, y, button)))
        return True

    def drag(
        self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5
    ) -> bool:
        self.calls.append(("drag", (start_x, start_y, end_x, end_y)))
        return True

    def scroll(self, x: int, y: int, clicks: int = 1) -> bool:
        return True

    def type_text(self, text: str, interval: float = 0.05) -> bool:
        return True

    def press_key(self, key: str) -> bool:
        return True

    # ── 坐标转换 ──

    def screen_to_window(self, x: int, y: int) -> tuple[int, int]:
        return (x - self._window.left, y - self._window.top)

    def window_to_screen(self, x: int, y: int) -> tuple[int, int]:
        return (x + self._window.left, y + self._window.top)

    def get_scale_factor(self) -> float:
        return 1.0


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def fake_adapter() -> FakePlatformAdapter:
    return FakePlatformAdapter()


@pytest.fixture
def low_hp_state() -> GameState:
    """血量低、金币充足 → 触发 emergency_level_up 规则。"""
    return GameState(
        phase=GamePhase.PREPARATION,
        round_number=3,
        stage=3,
        gold=10,
        hp=20,
        level=4,
    )


# ── Test ─────────────────────────────────────────────────────────────


async def test_rule_decision_then_execute(
    fake_adapter: FakePlatformAdapter, low_hp_state: GameState
) -> None:
    """decision_engine(rule) → action_executor 完整路径。"""

    # 1. 决策（无 LLM，纯规则）
    engine = HybridDecisionEngine(llm_client=None, use_som_annotation=False, llm_fallback=False)
    screenshot = Image.new("RGB", (1920, 1080))
    result = await engine.decide(screenshot, low_hp_state)

    assert result.source == "rule"
    assert result.action.type == ActionType.LEVEL_UP

    # 2. 执行
    executor = ActionExecutor(adapter=fake_adapter, humanize=False)
    exec_result = await executor.execute(result.action)

    assert exec_result.success
    assert exec_result.action.type == ActionType.LEVEL_UP

    # 3. 验证 adapter 收到了 click 调用
    click_calls = [c for c in fake_adapter.calls if c[0] == "click"]
    assert len(click_calls) == 1


async def test_vision_annotation_then_decision(
    fake_adapter: FakePlatformAdapter, low_hp_state: GameState
) -> None:
    """合成截图 → SoM 标注 → 决策 → 执行 完整路径。"""

    # 1. 合成截图 + SoM 标注
    fake_screenshot = Image.new("RGB", (1920, 1080), color=(30, 30, 30))
    annotator = SoMAnnotator()
    annotated, regions = annotator.create_full_annotation(fake_screenshot)

    assert annotated.size == (1920, 1080)
    assert "shop" in regions
    assert "board" in regions

    # 2. 决策（规则路径，不走 LLM）
    engine = HybridDecisionEngine(llm_client=None, use_som_annotation=False, llm_fallback=False)
    result = await engine.decide(annotated, low_hp_state)

    assert result.source == "rule"
    assert result.action.type == ActionType.LEVEL_UP

    # 3. 执行
    executor = ActionExecutor(adapter=fake_adapter, humanize=False)
    exec_result = await executor.execute(result.action)

    assert exec_result.success

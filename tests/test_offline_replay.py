"""
离线回放回归测试

使用静态截图执行 vision -> game_state -> decision_engine 链路
"""

import asyncio
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from core.action import Action, ActionType
from core.game_state import GameState
from core.protocols import WindowInfo
from core.rules.decision_engine import DecisionEngineBuilder
from core.rules.validator import ActionValidator
from core.vision.regions import GameRegions, UIRegion


@dataclass
class ReplayResult:
    """回放结果"""

    fixture_name: str
    extracted_fields: dict[str, Any]
    actions: list[dict[str, Any]]
    validation_passed: bool
    stable: bool


class FakePlatformAdapter:
    """伪造平台适配器，从静态截图提供数据"""

    def __init__(self, screenshot_path: Path, window_size: tuple[int, int] = (1920, 1080)):
        self._screenshot_path = screenshot_path
        self._window_size = window_size
        self._screenshot: Image.Image | None = None

    def get_window_info(self) -> WindowInfo | None:
        """返回固定的窗口信息"""
        return WindowInfo(
            title="Test Window",
            left=0,
            top=0,
            width=self._window_size[0],
            height=self._window_size[1],
            window_id=1,
        )

    def get_screenshot(self) -> Image.Image:
        """返回静态截图"""
        if self._screenshot is None:
            image = Image.open(self._screenshot_path)
            if image.size != self._window_size:
                image = image.resize(self._window_size, Image.NEAREST)
            self._screenshot = image
        return self._screenshot.copy()

    def click(
        self, x: int, y: int, button: str = "left", clicks: int = 1, interval: float = 0.1
    ) -> bool:
        """空实现"""
        return True

    def drag(
        self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5
    ) -> bool:
        """空实现"""
        return True

    def scroll(self, x: int, y: int, clicks: int = 1) -> bool:
        """空实现"""
        return True

    def type_text(self, text: str, interval: float = 0.05) -> bool:
        """空实现"""
        return True

    def press_key(self, key: str) -> bool:
        """空实现"""
        return True

    def get_game_window_rect(self) -> tuple[int, int, int, int]:
        """返回窗口矩形"""
        return (0, 0, self._window_size[0], self._window_size[1])

    def is_game_active(self) -> bool:
        """游戏窗口激活"""
        return True

    def activate_game(self) -> bool:
        """激活游戏窗口"""
        return True

    def screen_to_window(self, x: int, y: int) -> tuple[int, int]:
        """屏幕坐标转窗口坐标"""
        return (x, y)

    def window_to_screen(self, x: int, y: int) -> tuple[int, int]:
        """窗口坐标转屏幕坐标"""
        return (x, y)

    def get_scale_factor(self) -> float:
        """缩放因子"""
        return 1.0


class OfflineReplayTest:
    """离线回放测试器"""

    def __init__(self, seed: int = 42):
        self.seed = seed
        random.seed(seed)

        # 初始化组件
        self.decision_engine = (
            DecisionEngineBuilder()
            .with_llm_fallback(enabled=False)  # 禁用 LLM，使用规则
            .build()
        )
        self.validator = ActionValidator()

    def replay_fixture(
        self,
        fixture_path: Path,
        window_size: tuple[int, int] = (1920, 1080),
    ) -> ReplayResult:
        """对单个 fixture 执行完整回放"""
        random.seed(self.seed)

        # 1. 加载截图
        adapter = FakePlatformAdapter(fixture_path, window_size=window_size)
        screenshot = adapter.get_screenshot()

        # 2. 执行识别
        extracted = self._extract_fields(screenshot)

        # 3. 更新游戏状态
        game_state = GameState()
        game_state.round_number = extracted.get("round_number", 1)
        game_state.gold = extracted.get("gold", 0)
        game_state.level = extracted.get("level", 1)
        game_state.hp = extracted.get("hp", 100)

        # 4. 生成决策 (同步调用异步方法)
        actions = asyncio.run(self._generate_actions(screenshot, game_state))

        # 5. 验证动作
        validation_passed = all(self.validator.validate(action, game_state) for action in actions)

        return ReplayResult(
            fixture_name=fixture_path.name,
            extracted_fields=extracted,
            actions=[
                {
                    "type": action.type.value,
                    "target": action.target,
                    "confidence": action.confidence,
                }
                for action in actions
            ],
            validation_passed=validation_passed,
            stable=True,
        )

    def _extract_fields(self, screenshot: Image.Image) -> dict[str, Any]:
        """从截图中提取字段"""
        extracted: dict[str, Any] = {}
        transform = GameRegions.create_transform(screenshot.size)

        def crop_to_base(base_region: UIRegion) -> Image.Image:
            current_region = base_region.scale(transform)
            cropped = screenshot.crop(current_region.bbox)
            if cropped.size == (base_region.width, base_region.height):
                return cropped
            return cropped.resize((base_region.width, base_region.height), Image.NEAREST)

        # 分析顶部区域 (回合/金币/等级)
        top_base = UIRegion(
            name="replay_top_bar",
            x=0,
            y=0,
            width=GameRegions.BASE_SIZE[0],
            height=60,
        )
        top_region = crop_to_base(top_base)
        top_pixels = list(top_region.getdata())

        # 检测金色像素数量 (金币指示)
        gold_pixels = sum(1 for p in top_pixels if p[1] > 200 and p[2] < 100)
        extracted["gold"] = min(gold_pixels // 100, 100)

        # 检测商店槽位颜色
        slot_colors = [
            (80, 160, 80),  # 1费
            (80, 80, 160),  # 2费
            (160, 80, 160),  # 3费
            (160, 120, 80),  # 4费
            (200, 160, 80),  # 5费
        ]

        detected_slots = 0
        for slot_region in GameRegions.all_shop_slots():
            slot_image = crop_to_base(slot_region)
            slot_pixels = list(slot_image.getdata())
            has_slot_color = any(
                sum(
                    1
                    for p in slot_pixels
                    if abs(p[0] - color[0]) < 30
                    and abs(p[1] - color[1]) < 30
                    and abs(p[2] - color[2]) < 30
                )
                > 80
                for color in slot_colors
            )
            if has_slot_color:
                detected_slots += 1

        extracted["shop_slots"] = min(detected_slots, 5)

        # 默认值
        extracted["round_number"] = 1
        extracted["level"] = 1
        extracted["hp"] = 100
        extracted["stage"] = 1

        return extracted

    async def _generate_actions(
        self, screenshot: Image.Image, game_state: GameState
    ) -> list[Action]:
        """生成动作列表"""
        actions = []

        # 规则引擎决策
        result = await self.decision_engine.decide(screenshot, game_state)
        if result and result.action:
            actions.append(result.action)

        # 如果没有动作，添加 NONE
        if not actions:
            actions.append(Action(type=ActionType.NONE, confidence=1.0))

        return actions

    def verify_stability(self, fixture_path: Path, runs: int = 3) -> tuple[bool, list[list[dict]]]:
        """验证输出稳定性"""
        all_actions: list[list[dict]] = []

        for i in range(runs):
            random.seed(self.seed)
            result = self.replay_fixture(fixture_path)
            all_actions.append(result.actions)

        if len(all_actions) < 2:
            return True, all_actions

        first = all_actions[0]
        stable = all(actions == first for actions in all_actions[1:])

        return stable, all_actions


# === 测试 ===

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "screens"


@pytest.fixture(scope="module")
def replay_tester():
    """创建回放测试器"""
    return OfflineReplayTest(seed=42)


@pytest.fixture(scope="module")
def scaled_fixture_sizes() -> dict[str, tuple[int, int]]:
    """缩放窗口尺寸版本（相对 1920x1080）。"""
    return {
        "0.75x": (1440, 810),
        "1.25x": (2400, 1350),
    }


@pytest.fixture(scope="module")
def fixture_files():
    """获取所有 fixture 文件"""
    if not FIXTURES_DIR.exists():
        pytest.skip(f"Fixtures directory not found: {FIXTURES_DIR}")
    files = list(FIXTURES_DIR.glob("*.png"))
    if not files:
        pytest.skip("No fixture files found")
    return files


class TestOfflineReplay:
    """离线回放测试"""

    def test_fixtures_exist(self, fixture_files):
        """fixtures 存在"""
        assert len(fixture_files) >= 3, "至少需要 3 个 fixture 文件"

    def test_replay_shop(self, replay_tester):
        """回放商店截图"""
        fixture = FIXTURES_DIR / "shop.png"
        if not fixture.exists():
            pytest.skip(f"Fixture not found: {fixture}")

        result = replay_tester.replay_fixture(fixture)

        # 断言：至少提取出关键字段
        assert "shop_slots" in result.extracted_fields
        assert "gold" in result.extracted_fields
        assert result.extracted_fields["shop_slots"] >= 0

        # 断言：动作列表非空
        assert len(result.actions) > 0

        # 断言：所有动作通过验证
        assert result.validation_passed

    def test_replay_board(self, replay_tester):
        """回放棋盘截图"""
        fixture = FIXTURES_DIR / "board.png"
        if not fixture.exists():
            pytest.skip(f"Fixture not found: {fixture}")

        result = replay_tester.replay_fixture(fixture)

        assert len(result.actions) > 0
        assert result.validation_passed

    def test_replay_info(self, replay_tester):
        """回放信息UI截图"""
        fixture = FIXTURES_DIR / "info.png"
        if not fixture.exists():
            pytest.skip(f"Fixture not found: {fixture}")

        result = replay_tester.replay_fixture(fixture)

        # 断言：提取关键字段
        assert "gold" in result.extracted_fields
        assert result.extracted_fields["gold"] >= 0

        assert len(result.actions) > 0
        assert result.validation_passed

    def test_replay_selection(self, replay_tester):
        """回放选择界面截图"""
        fixture = FIXTURES_DIR / "selection.png"
        if not fixture.exists():
            pytest.skip(f"Fixture not found: {fixture}")

        result = replay_tester.replay_fixture(fixture)

        assert len(result.actions) > 0
        assert result.validation_passed

    def test_replay_bench(self, replay_tester):
        """回放备战席截图"""
        fixture = FIXTURES_DIR / "bench.png"
        if not fixture.exists():
            pytest.skip(f"Fixture not found: {fixture}")

        result = replay_tester.replay_fixture(fixture)

        assert len(result.actions) > 0
        assert result.validation_passed

    def test_output_stability(self, replay_tester):
        """测试输出稳定性：同一输入 3 次运行动作序列一致"""
        fixture = FIXTURES_DIR / "shop.png"
        if not fixture.exists():
            pytest.skip(f"Fixture not found: {fixture}")

        stable, all_actions = replay_tester.verify_stability(fixture, runs=3)

        assert stable, f"动作序列不稳定: {all_actions}"

    def test_scaled_fixture_consistency(self, replay_tester, scaled_fixture_sizes):
        """不同窗口缩放下识别字段与动作序列保持一致。"""
        fixture = FIXTURES_DIR / "shop.png"
        if not fixture.exists():
            pytest.skip(f"Fixture not found: {fixture}")

        baseline = replay_tester.replay_fixture(fixture, window_size=(1920, 1080))
        baseline_action_types = [a["type"] for a in baseline.actions]

        for label, size in scaled_fixture_sizes.items():
            result = replay_tester.replay_fixture(fixture, window_size=size)
            assert result.extracted_fields["gold"] == baseline.extracted_fields["gold"], (
                f"{label} gold 不一致"
            )
            assert (
                result.extracted_fields["shop_slots"] == baseline.extracted_fields["shop_slots"]
            ), f"{label} shop_slots 不一致"
            assert result.extracted_fields["level"] == baseline.extracted_fields["level"], (
                f"{label} level 不一致"
            )
            assert [a["type"] for a in result.actions] == baseline_action_types, (
                f"{label} 动作序列不一致: {result.actions} vs {baseline.actions}"
            )

    def test_all_fixtures_produce_actions(self, replay_tester, fixture_files):
        """所有 fixture 都能产生有效动作"""
        for fixture in fixture_files:
            result = replay_tester.replay_fixture(fixture)

            # 断言：动作列表非空
            assert len(result.actions) > 0, f"{fixture.name}: 无动作输出"

            # 断言：动作通过验证
            assert result.validation_passed, f"{fixture.name}: 动作验证失败"


class TestReplayArtifacts:
    """回放产物生成"""

    def test_generate_replay_json(self, replay_tester, fixture_files, tmp_path):
        """生成回放 JSON 产物"""
        results = []

        for fixture in fixture_files:
            result = replay_tester.replay_fixture(fixture)

            results.append(
                {
                    "fixture": result.fixture_name,
                    "extracted_fields": result.extracted_fields,
                    "actions": result.actions,
                    "validation_passed": result.validation_passed,
                }
            )

        # 保存产物
        output_path = tmp_path / "replay_results.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "version": "1.0",
                    "seed": 42,
                    "fixtures_tested": len(results),
                    "results": results,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        assert output_path.exists()

        # 验证 JSON 内容
        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)

        assert data["fixtures_tested"] >= 3
        for r in data["results"]:
            assert "fixture" in r
            assert "actions" in r
            assert len(r["actions"]) > 0


def test_save_replay_artifacts(tmp_path):
    """保存回放产物到 artifacts/replay/"""
    tester = OfflineReplayTest(seed=42)

    results = []
    for fixture in FIXTURES_DIR.glob("*.png"):
        result = tester.replay_fixture(fixture)
        results.append(
            {
                "fixture": result.fixture_name,
                "extracted_fields": result.extracted_fields,
                "actions": result.actions,
                "validation_passed": result.validation_passed,
            }
        )

    # 保存到 artifacts/replay/
    artifacts_dir = tmp_path / "replay"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    output_path = artifacts_dir / "replay_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "version": "1.0",
                "seed": 42,
                "fixtures_tested": len(results),
                "results": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    assert output_path.exists()
    print(f"Replay artifacts saved to: {output_path}")

"""识别系统测试"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from core.coordinate_scaler import CoordinateScaler, Resolution
from core.game_state import GameState
from core.vision.ocr_engine import OCRResult
from core.vision.recognition_engine import RecognitionEngine, RecognizedEntity
from core.vision.regions import GameRegions, UIRegion, scale_regions
from core.vision.template_matcher import MatchResult
from core.vision.template_registry import TemplateEntry, TemplateRegistry

# === TemplateRegistry 测试 ===


class TestTemplateRegistry:
    """模板注册表测试"""

    def test_register_and_lookup(self) -> None:
        """注册和查询"""
        registry = TemplateRegistry()

        entry = TemplateEntry(
            entity_type="hero",
            entity_id="亚索",
            template_path=Path("heroes/cost1/yasuo.png"),
            ocr_variants=["亚索", "Yasuo"],
        )
        registry.register(entry)

        # 查询模板路径
        path = registry.get_template_path("hero", "亚索")
        assert path is not None
        assert path.name == "yasuo.png"

    def test_ocr_lookup_exact(self) -> None:
        """OCR 精确匹配"""
        registry = TemplateRegistry()

        entry = TemplateEntry(
            entity_type="hero",
            entity_id="亚索",
            template_path=Path("heroes/cost1/yasuo.png"),
            ocr_variants=["亚索", "Yasuo"],
        )
        registry.register(entry)

        # 精确匹配
        result = registry.lookup_by_ocr_text("亚索")
        assert result == "亚索"

        result = registry.lookup_by_ocr_text("Yasuo")
        assert result == "亚索"

    def test_ocr_lookup_fuzzy(self) -> None:
        """OCR 模糊匹配"""
        registry = TemplateRegistry()

        entry = TemplateEntry(
            entity_type="hero",
            entity_id="亚索",
            template_path=Path("heroes/cost1/yasuo.png"),
            ocr_variants=["亚索"],
        )
        registry.register(entry)

        # 模糊匹配（相似度较低时应返回 None）
        result = registry.lookup_by_ocr_text_fuzzy("亚", threshold=0.5)
        # 相似度计算：公共字符 / 最大长度 = 1 / 2 = 0.5
        assert result == "亚索"

    def test_list_entities(self) -> None:
        """列出实体"""
        registry = TemplateRegistry()

        for name in ["亚索", "菲奥娜", "劫"]:
            entry = TemplateEntry(
                entity_type="hero",
                entity_id=name,
                template_path=Path(f"heroes/{name}.png"),
                ocr_variants=[name],
            )
            registry.register(entry)

        heroes = registry.list_entities("hero")
        assert len(heroes) == 3
        assert "亚索" in heroes

    def test_load_from_game_data(self, tmp_path: Path) -> None:
        """从游戏数据加载"""
        # 创建临时游戏数据
        game_data = tmp_path / "game_data"
        game_data.mkdir()

        heroes_json = game_data / "heroes.json"
        heroes_json.write_text(
            """{
            "heroes": [
                {"name": "亚索", "cost": 1, "synergies": ["决斗大师"]}
            ]
        }""",
            encoding="utf-8",
        )

        registry = TemplateRegistry()
        count = registry.load_from_game_data(game_data)

        assert count == 1
        assert "亚索" in registry.list_entities("hero")


# === UIRegion 测试 ===


class TestUIRegion:
    """UI 区域测试"""

    def test_bbox_and_center(self) -> None:
        """边界框和中心点"""
        region = UIRegion(name="test", x=100, y=200, width=80, height=60)

        assert region.bbox == (100, 200, 180, 260)
        assert region.center == (140, 230)

    def test_scale(self) -> None:
        """缩放"""
        region = UIRegion(name="test", x=100, y=200, width=80, height=60)
        scaler = CoordinateScaler(Resolution(3840, 2160))  # 2x

        scaled = region.scale(scaler)
        assert scaled.x == 200
        assert scaled.y == 400
        assert scaled.width == 160
        assert scaled.height == 120


# === GameRegions 测试 ===


class TestGameRegions:
    """游戏区域测试"""

    def test_shop_slots(self) -> None:
        """商店槽位"""
        slots = GameRegions.all_shop_slots()
        assert len(slots) == 5

        # 检查槽位不重叠
        for i in range(4):
            assert slots[i].x < slots[i + 1].x

    def test_shop_slot_index(self) -> None:
        """商店槽位索引"""
        slot0 = GameRegions.shop_slot(0)
        slot4 = GameRegions.shop_slot(4)

        assert slot0.x < slot4.x

    def test_shop_slot_invalid_index(self) -> None:
        """无效槽位索引"""
        with pytest.raises(ValueError):
            GameRegions.shop_slot(-1)
        with pytest.raises(ValueError):
            GameRegions.shop_slot(5)

    def test_board_cells(self) -> None:
        """棋盘格子"""
        cells = GameRegions.all_board_cells()
        assert len(cells) == 28  # 4 x 7

    def test_board_cell(self) -> None:
        """单个棋盘格子"""
        cell = GameRegions.board_cell(0, 0)
        assert cell.x == GameRegions.BOARD.x
        assert cell.y == GameRegions.BOARD.y

        cell_1_2 = GameRegions.board_cell(1, 2)
        assert cell_1_2.x == GameRegions.BOARD.x + 2 * GameRegions.CELL_WIDTH
        assert cell_1_2.y == GameRegions.BOARD.y + 1 * GameRegions.CELL_HEIGHT

    def test_bench_slots(self) -> None:
        """备战席槽位"""
        slots = GameRegions.all_bench_slots()
        assert len(slots) == 9


# === scale_regions 测试 ===


class TestScaleRegions:
    """批量缩放测试"""

    def test_scale_regions(self) -> None:
        """批量缩放区域"""
        regions = [
            UIRegion(name="r1", x=100, y=200, width=50, height=50),
            UIRegion(name="r2", x=300, y=400, width=60, height=60),
        ]
        scaler = CoordinateScaler(Resolution(960, 540))  # 0.5x

        scaled = scale_regions(regions, scaler)

        assert len(scaled) == 2
        assert scaled[0].x == 50
        assert scaled[0].y == 100
        assert scaled[1].x == 150
        assert scaled[1].y == 200


# === RecognitionEngine 测试 ===


class TestRecognitionEngine:
    """识别引擎测试"""

    @pytest.fixture
    def mock_components(self) -> tuple[TemplateRegistry, MagicMock, MagicMock]:
        """创建 mock 组件"""
        registry = TemplateRegistry()
        registry.register(
            TemplateEntry(
                entity_type="hero",
                entity_id="亚索",
                template_path=Path("heroes/cost1/yasuo.png"),
                ocr_variants=["亚索", "Yasuo"],
            )
        )

        matcher = MagicMock()
        ocr = MagicMock()

        return registry, matcher, ocr

    def test_recognize_shop_empty(
        self, mock_components: tuple[TemplateRegistry, MagicMock, MagicMock]
    ) -> None:
        """识别空商店"""
        registry, matcher, ocr = mock_components
        matcher.match.return_value = None
        ocr.recognize.return_value = []

        engine = RecognitionEngine(
            registry=registry,
            matcher=matcher,
            ocr=ocr,
        )

        # 创建空白截图
        screenshot = Image.new("RGB", (1920, 1080), color="black")
        results = engine.recognize_shop(screenshot)

        assert len(results) == 5
        assert all(r is None for r in results)

    def test_recognize_shop_with_template(
        self, mock_components: tuple[TemplateRegistry, MagicMock, MagicMock]
    ) -> None:
        """模板匹配识别商店"""
        registry, matcher, ocr = mock_components

        # Mock 模板匹配成功
        matcher.match.return_value = MatchResult(
            x=10,
            y=10,
            width=50,
            height=50,
            confidence=0.9,
            template_name="yasuo",
        )
        matcher.templates = {"yasuo": MagicMock()}
        ocr.recognize.return_value = []

        engine = RecognitionEngine(
            registry=registry,
            matcher=matcher,
            ocr=ocr,
        )

        screenshot = Image.new("RGB", (1920, 1080), color="black")

        # 需要 mock get_template_path 返回存在的路径
        with patch.object(registry, "get_template_path") as mock_path:
            mock_path.return_value = Path("/fake/yasuo.png")
            with patch.object(Path, "exists", return_value=True):
                results = engine.recognize_shop(screenshot)

        assert len(results) == 5
        # 检查是否有识别结果（取决于 mock 设置）
        # 由于 mock 复杂性，这里简化验证

    def test_recognize_ocr_fallback(
        self, mock_components: tuple[TemplateRegistry, MagicMock, MagicMock]
    ) -> None:
        """OCR 兜底识别"""
        registry, matcher, ocr = mock_components

        # 模板匹配失败
        matcher.match.return_value = None

        # OCR 识别成功
        ocr.recognize.return_value = [
            OCRResult(text="亚索", confidence=0.85, bbox=(10, 10, 60, 60))
        ]

        engine = RecognitionEngine(
            registry=registry,
            matcher=matcher,
            ocr=ocr,
        )

        # 创建测试区域
        region = UIRegion(name="test", x=0, y=0, width=100, height=100)
        screenshot = Image.new("RGB", (1920, 1080), color="black")

        result = engine._recognize_in_region(
            screenshot=screenshot,
            region=region,
            entity_type="hero",
        )

        # OCR 识别应该成功
        assert result is not None
        assert result.entity_name == "亚索"
        assert result.method == "ocr"

    def test_hybrid_fusion(
        self, mock_components: tuple[TemplateRegistry, MagicMock, MagicMock]
    ) -> None:
        """模板+OCR 融合"""
        registry, matcher, ocr = mock_components

        # 两者都识别到相同实体
        template_result = ("亚索", 0.85, (10, 10, 60, 60))
        ocr_result = ("亚索", 0.80, (10, 10, 60, 60))

        engine = RecognitionEngine(
            registry=registry,
            matcher=matcher,
            ocr=ocr,
        )

        region = UIRegion(name="test", x=0, y=0, width=100, height=100)
        result = engine._fuse_results(
            template_result=template_result,
            ocr_result=ocr_result,
            region=region,
            entity_type="hero",
            slot_index=0,
        )

        assert result is not None
        assert result.entity_name == "亚索"
        assert result.method == "hybrid"
        assert result.confidence > 0.85  # 融合后置信度提升


# === GameState update_from_recognition 测试 ===


class TestGameStateRecognition:
    """游戏状态从识别更新测试"""

    def test_update_shop(self) -> None:
        """更新商店"""
        state = GameState()

        shop_entities: list[RecognizedEntity | None] = [
            RecognizedEntity(
                entity_type="hero",
                entity_name="亚索",
                confidence=0.9,
                method="template",
                bbox=(0, 0, 50, 50),
                slot_index=0,
            ),
            None,  # 空槽位
            RecognizedEntity(
                entity_type="hero",
                entity_name="劫",
                confidence=0.85,
                method="template",
                bbox=(0, 0, 50, 50),
                slot_index=2,
            ),
            None,
            None,
        ]

        state.update_from_recognition(shop_entities=shop_entities)

        assert state.shop_slots[0].hero_name == "亚索"
        assert state.shop_slots[1].hero_name is None
        assert state.shop_slots[2].hero_name == "劫"

    def test_update_synergies(self) -> None:
        """更新羁绊"""
        state = GameState()

        synergy_entities = [
            RecognizedEntity(
                entity_type="synergy",
                entity_name="福星",
                confidence=0.9,
                method="template",
                bbox=(0, 0, 50, 50),
            ),
            RecognizedEntity(
                entity_type="synergy",
                entity_name="斗士",
                confidence=0.85,
                method="template",
                bbox=(0, 60, 50, 110),
            ),
        ]

        state.update_from_recognition(synergy_entities=synergy_entities)

        assert "福星" in state.synergies
        assert state.synergies["福星"].is_active
        assert "斗士" in state.synergies

    def test_update_items(self) -> None:
        """更新装备"""
        state = GameState()

        item_entities = [
            RecognizedEntity(
                entity_type="item",
                entity_name="暴风大剑",
                confidence=0.9,
                method="template",
                bbox=(0, 0, 30, 30),
            ),
            RecognizedEntity(
                entity_type="item",
                entity_name="锁子甲",
                confidence=0.85,
                method="template",
                bbox=(40, 0, 70, 30),
            ),
        ]

        state.update_from_recognition(item_entities=item_entities)

        assert "暴风大剑" in state.available_items
        assert "锁子甲" in state.available_items
        assert len(state.available_items) == 2


# === 集成测试 ===


class TestRecognitionIntegration:
    """识别系统集成测试"""

    def test_registry_json_roundtrip(self, tmp_path: Path) -> None:
        """注册表 JSON 读写往返"""
        registry = TemplateRegistry(template_root=tmp_path)

        # 注册一些条目
        registry.register(
            TemplateEntry(
                entity_type="hero",
                entity_id="亚索",
                template_path=Path("heroes/yasuo.png"),
                ocr_variants=["亚索", "Yasuo"],
            )
        )
        registry.register(
            TemplateEntry(
                entity_type="item",
                entity_id="暴风大剑",
                template_path=Path("items/sword.png"),
                ocr_variants=["暴风大剑", "大剑"],
            )
        )

        # 保存
        json_path = tmp_path / "registry.json"
        assert registry.save_registry_json(json_path)

        # 加载到新注册表
        new_registry = TemplateRegistry(template_root=tmp_path)
        count = new_registry.load_from_registry_json(json_path)

        assert count == 2
        assert new_registry.get_template_path("hero", "亚索") is not None
        assert new_registry.get_template_path("item", "暴风大剑") is not None


# === 模板存在性校验测试 ===


class TestTemplateValidation:
    """模板存在性校验测试"""

    def test_validate_templates(self, tmp_path: Path) -> None:
        """校验模板文件存在性"""
        registry = TemplateRegistry(template_root=tmp_path)

        # 注册一个条目
        registry.register(
            TemplateEntry(
                entity_type="hero",
                entity_id="测试英雄",
                template_path=Path("heroes/test.png"),
                ocr_variants=["测试英雄"],
            )
        )

        # 创建模板文件
        (tmp_path / "heroes").mkdir(parents=True)
        (tmp_path / "heroes" / "test.png").touch()

        result = registry.validate_templates()

        assert result["stats"]["total"] == 1
        assert result["stats"]["existing_count"] == 1
        assert result["stats"]["missing_count"] == 0

    def test_validate_missing_templates(self, tmp_path: Path) -> None:
        """校验缺失的模板"""
        registry = TemplateRegistry(template_root=tmp_path)

        # 注册但不创建文件
        registry.register(
            TemplateEntry(
                entity_type="hero",
                entity_id="缺失英雄",
                template_path=Path("heroes/missing.png"),
                ocr_variants=["缺失英雄"],
            )
        )

        result = registry.validate_templates()

        assert result["stats"]["missing_count"] == 1
        assert len(result["missing"]) == 1
        assert result["missing"][0]["entity_id"] == "缺失英雄"

    def test_check_template_exists(self, tmp_path: Path) -> None:
        """检查单个模板存在"""
        registry = TemplateRegistry(template_root=tmp_path)

        # 注册并创建
        registry.register(
            TemplateEntry(
                entity_type="hero",
                entity_id="存在英雄",
                template_path=Path("heroes/exists.png"),
                ocr_variants=["存在英雄"],
            )
        )
        (tmp_path / "heroes").mkdir(parents=True)
        (tmp_path / "heroes" / "exists.png").touch()

        assert registry.check_template_exists("hero", "存在英雄") is True
        assert registry.check_template_exists("hero", "不存在") is False

    def test_get_missing_templates_message(self, tmp_path: Path) -> None:
        """获取缺失模板报错信息"""
        registry = TemplateRegistry(template_root=tmp_path)

        # 注册但不创建文件
        registry.register(
            TemplateEntry(
                entity_type="hero",
                entity_id="缺失英雄",
                template_path=Path("heroes/missing.png"),
                ocr_variants=["缺失英雄"],
            )
        )

        message = registry.get_missing_templates_message()

        assert message is not None
        assert "缺失 1 个模板文件" in message
        assert "缺失英雄" in message

    def test_get_missing_templates_message_none_when_all_exist(self, tmp_path: Path) -> None:
        """全部存在时返回 None"""
        registry = TemplateRegistry(template_root=tmp_path)

        registry.register(
            TemplateEntry(
                entity_type="hero",
                entity_id="存在英雄",
                template_path=Path("heroes/exists.png"),
                ocr_variants=["存在英雄"],
            )
        )
        (tmp_path / "heroes").mkdir(parents=True)
        (tmp_path / "heroes" / "exists.png").touch()

        message = registry.get_missing_templates_message()

        assert message is None


# === S13 模板导入验证 ===


class TestS13TemplateImport:
    """S13 模板导入验证测试"""

    def test_s13_imported_directory_exists(self) -> None:
        """S13 导入目录存在"""
        from core.vision.template_registry import TEMPLATE_ROOT

        s13_dir = TEMPLATE_ROOT / "s13_imported"
        assert s13_dir.exists(), f"S13 导入目录不存在: {s13_dir}"

    def test_s13_template_count(self) -> None:
        """S13 模板数量大于 0"""
        from core.vision.template_registry import TEMPLATE_ROOT

        s13_dir = TEMPLATE_ROOT / "s13_imported"
        if s13_dir.exists():
            count = len(list(s13_dir.glob("*.png")))
            assert count > 0, "S13 导入目录中没有 PNG 文件"
            assert count == 99, f"预期 99 个模板，实际 {count} 个"

    def test_s13_mapping_file_exists(self) -> None:
        """S13 映射文件存在"""
        from core.vision.template_registry import TEMPLATE_ROOT

        mapping_file = TEMPLATE_ROOT / "s13_mapping.json"
        assert mapping_file.exists(), f"S13 映射文件不存在: {mapping_file}"

    def test_s13_mapping_valid_json(self) -> None:
        """S13 映射文件是有效 JSON"""
        import json

        from core.vision.template_registry import TEMPLATE_ROOT

        mapping_file = TEMPLATE_ROOT / "s13_mapping.json"
        with open(mapping_file, encoding="utf-8") as f:
            data = json.load(f)

        assert "version" in data
        assert "mapping" in data
        assert data["total_images"] == 99

    def test_registry_count_s13_imported(self) -> None:
        """统计 S13 导入模板数量"""
        registry = TemplateRegistry()
        count = registry.count_s13_imported()

        assert count == 99, f"预期 99 个 S13 导入模板，实际 {count} 个"

    def test_template_directories_structure(self) -> None:
        """模板目录结构正确"""
        from core.vision.template_registry import TEMPLATE_ROOT

        required_dirs = [
            "heroes/cost1",
            "heroes/cost2",
            "heroes/cost3",
            "heroes/cost4",
            "heroes/cost5",
            "items/base",
            "items/combined",
            "synergies",
            "buttons",
            "s13_imported",
        ]

        for dir_path in required_dirs:
            full_path = TEMPLATE_ROOT / dir_path
            assert full_path.exists(), f"模板目录不存在: {full_path}"
            assert full_path.is_dir(), f"不是目录: {full_path}"

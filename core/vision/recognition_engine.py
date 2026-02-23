"""
识别引擎

组合模板匹配 + OCR，识别游戏中的英雄、装备、羁绊
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from core.coordinate_scaler import CoordinateScaler
from core.geometry.transform import CoordinateTransform
from core.vision.ocr_engine import OCREngine
from core.vision.regions import UIRegion
from core.vision.template_matcher import TemplateMatcher
from core.vision.template_registry import TemplateRegistry

logger = logging.getLogger("recognition_engine")


@dataclass
class RecognizedEntity:
    """识别出的实体"""

    entity_type: str  # "hero" / "item" / "synergy"
    entity_name: str  # 实体名称
    confidence: float  # 置信度
    method: str  # "template" / "ocr" / "hybrid"
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    slot_index: int | None = None  # 槽位索引（商店/备战席）

    @property
    def center(self) -> tuple[int, int]:
        """获取中心点"""
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    @property
    def width(self) -> int:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> int:
        return self.bbox[3] - self.bbox[1]


class RecognitionEngine:
    """
    识别引擎

    结合模板匹配和 OCR 识别游戏实体
    """

    def __init__(
        self,
        registry: TemplateRegistry,
        matcher: TemplateMatcher,
        ocr: OCREngine,
        scaler: CoordinateScaler | None = None,
        template_threshold: float = 0.75,
        ocr_confidence_threshold: float = 0.6,
    ):
        """
        初始化识别引擎

        Args:
            registry: 模板注册表
            matcher: 模板匹配器
            ocr: OCR 引擎
            scaler: 坐标缩放器
            template_threshold: 模板匹配置信度阈值
            ocr_confidence_threshold: OCR 置信度阈值
        """
        self.registry = registry
        self.matcher = matcher
        self.ocr = ocr
        self.scaler = scaler or CoordinateScaler()
        self.transform = self._make_transform_from_scaler(self.scaler)
        self.template_threshold = template_threshold
        self.ocr_confidence_threshold = ocr_confidence_threshold

    def _make_transform_from_scaler(self, scaler: CoordinateScaler) -> CoordinateTransform:
        """兼容旧接口：从 CoordinateScaler 构造统一坐标变换。"""
        if hasattr(scaler, "transform"):
            return scaler.transform

        return CoordinateTransform(
            base_size=(CoordinateScaler.REFERENCE.width, CoordinateScaler.REFERENCE.height),
            current_size=(scaler.target.width, scaler.target.height),
            content_rect=(0, 0, scaler.target.width, scaler.target.height),
        )

    def _update_transform(self, screenshot: Image.Image) -> None:
        """根据截图实际尺寸更新统一坐标映射。"""
        from core.vision.regions import GameRegions

        w, h = screenshot.size
        if (w, h) != self.transform.current_size:
            self.transform = GameRegions.create_transform((w, h))
            self.scaler = CoordinateScaler.from_window_size(w, h)

    def _update_scaler(self, screenshot: Image.Image) -> None:
        """兼容旧调用名。"""
        self._update_transform(screenshot)

    def _map_region(self, base_region: UIRegion) -> UIRegion:
        """将基准区域映射到当前截图坐标。"""
        return base_region.scale(self.transform)

    def _normalize_crop_to_base(self, cropped: Image.Image, base_region: UIRegion) -> Image.Image:
        """将当前 ROI 统一缩放回基准区域尺寸，提升模板/OCR一致性。"""
        target_size = (base_region.width, base_region.height)
        if cropped.size == target_size:
            return cropped
        return cropped.resize(target_size, Image.LANCZOS)

    def _map_local_bbox_to_global(
        self,
        local_bbox: tuple[int, int, int, int],
        current_region: UIRegion,
        base_region: UIRegion,
    ) -> tuple[int, int, int, int]:
        """将基准 ROI 内局部 bbox 映射回当前截图全局坐标。"""
        local_transform = CoordinateTransform(
            base_size=(base_region.width, base_region.height),
            current_size=(current_region.width, current_region.height),
            content_rect=(0, 0, current_region.width, current_region.height),
        )
        x1, y1 = local_transform.map_point((local_bbox[0], local_bbox[1]))
        x2, y2 = local_transform.map_point((local_bbox[2], local_bbox[3]))
        return (
            current_region.x + x1,
            current_region.y + y1,
            current_region.x + x2,
            current_region.y + y2,
        )

    def recognize_shop(
        self,
        screenshot: Image.Image,
        shop_regions: list[UIRegion] | None = None,
    ) -> list[RecognizedEntity | None]:
        """
        识别商店中的英雄

        Args:
            screenshot: 游戏截图
            shop_regions: 商店槽位区域列表（5个），None 则使用默认区域

        Returns:
            识别结果列表（5个元素，空槽位返回 None）
        """
        from core.vision.regions import GameRegions

        self._update_transform(screenshot)

        if shop_regions is None:
            shop_regions = GameRegions.all_shop_slots()

        results: list[RecognizedEntity | None] = []

        for idx, base_region in enumerate(shop_regions):
            region = self._map_region(base_region)
            entity = self._recognize_in_region(
                screenshot=screenshot,
                region=region,
                base_region=base_region,
                entity_type="hero",
                slot_index=idx,
            )
            results.append(entity)

        return results

    def recognize_board(
        self,
        screenshot: Image.Image,
        board_region: UIRegion | None = None,
    ) -> list[RecognizedEntity]:
        """
        识别棋盘上的英雄

        Args:
            screenshot: 游戏截图
            board_region: 棋盘区域

        Returns:
            识别出的英雄列表
        """
        from core.vision.regions import GameRegions

        self._update_transform(screenshot)

        if board_region is None:
            board_region = GameRegions.BOARD

        _ = self._map_region(board_region)  # 缩放参数验证
        results: list[RecognizedEntity] = []

        # 遍历所有格子
        for row in range(4):
            for col in range(7):
                cell = GameRegions.board_cell(row, col)
                scaled_cell = self._map_region(cell)

                entity = self._recognize_in_region(
                    screenshot=screenshot,
                    region=scaled_cell,
                    base_region=cell,
                    entity_type="hero",
                )
                if entity:
                    results.append(entity)

        return results

    def recognize_synergies(
        self,
        screenshot: Image.Image,
        synergy_region: UIRegion | None = None,
    ) -> list[RecognizedEntity]:
        """
        识别激活的羁绊

        Args:
            screenshot: 游戏截图
            synergy_region: 羁绊区域

        Returns:
            识别出的羁绊列表
        """
        from core.vision.regions import GameRegions

        self._update_transform(screenshot)

        if synergy_region is None:
            synergy_region = GameRegions.SYNERGY_BADGES

        scaled_region = self._map_region(synergy_region)
        results: list[RecognizedEntity] = []

        # 裁剪羁绊区域
        cropped = screenshot.crop(scaled_region.bbox)
        normalized = self._normalize_crop_to_base(cropped, synergy_region)

        # 对每个羁绊模板进行匹配
        for synergy_name in self.registry.list_entities("synergy"):
            template_path = self.registry.get_template_path("synergy", synergy_name)
            if template_path and template_path.exists():
                # 使用模板匹配
                match = self.matcher.match(
                    image=normalized,
                    template_name=template_path.stem,
                    threshold=self.template_threshold,
                )
                if match:
                    bbox = self._map_local_bbox_to_global(match.bbox, scaled_region, synergy_region)
                    results.append(
                        RecognizedEntity(
                            entity_type="synergy",
                            entity_name=synergy_name,
                            confidence=match.confidence,
                            method="template",
                            bbox=bbox,
                        )
                    )

        # 按 y 坐标排序（从上到下）
        results.sort(key=lambda e: e.bbox[1])
        return results

    def recognize_items(
        self,
        screenshot: Image.Image,
        item_regions: list[UIRegion] | None = None,
    ) -> list[RecognizedEntity]:
        """
        识别装备栏中的装备

        Args:
            screenshot: 游戏截图
            item_regions: 装备槽位区域列表

        Returns:
            识别出的装备列表
        """
        from core.vision.regions import GameRegions

        self._update_transform(screenshot)

        if item_regions is None:
            item_regions = [GameRegions.item_slot(i) for i in range(10)]

        results: list[RecognizedEntity] = []

        for idx, base_region in enumerate(item_regions):
            region = self._map_region(base_region)
            entity = self._recognize_in_region(
                screenshot=screenshot,
                region=region,
                base_region=base_region,
                entity_type="item",
                slot_index=idx,
            )
            if entity:
                results.append(entity)

        return results

    def recognize_bench(
        self,
        screenshot: Image.Image,
        bench_regions: list[UIRegion] | None = None,
    ) -> list[RecognizedEntity | None]:
        """
        识别备战席上的英雄

        Args:
            screenshot: 游戏截图
            bench_regions: 备战席槽位区域列表

        Returns:
            识别结果列表（9个元素，空槽位返回 None）
        """
        from core.vision.regions import GameRegions

        self._update_transform(screenshot)

        if bench_regions is None:
            bench_regions = GameRegions.all_bench_slots()

        results: list[RecognizedEntity | None] = []

        for idx, base_region in enumerate(bench_regions):
            region = self._map_region(base_region)
            entity = self._recognize_in_region(
                screenshot=screenshot,
                region=region,
                base_region=base_region,
                entity_type="hero",
                slot_index=idx,
            )
            results.append(entity)

        return results

    def recognize_player_info(
        self,
        screenshot: Image.Image,
    ) -> dict[str, int | None]:
        """识别金币和等级数字"""
        from core.vision.regions import GameRegions

        self._update_transform(screenshot)
        result: dict[str, int | None] = {"gold": None, "level": None}

        regions = [("gold", GameRegions.GOLD_DISPLAY), ("level", GameRegions.LEVEL_DISPLAY)]
        for key, base_region in regions:
            scaled = self._map_region(base_region)
            crop = screenshot.crop(scaled.bbox)
            normalized = self._normalize_crop_to_base(crop, base_region)
            # 小图放大 3x 提高 OCR 识别率
            big = normalized.resize((normalized.width * 3, normalized.height * 3), Image.LANCZOS)
            result[key] = self.ocr.recognize_number(big)

        return result

    def _recognize_in_region(
        self,
        screenshot: Image.Image,
        region: UIRegion,
        entity_type: str,
        base_region: UIRegion | None = None,
        slot_index: int | None = None,
    ) -> RecognizedEntity | None:
        """
        在指定区域内识别实体

        Args:
            screenshot: 截图
            region: 区域
            entity_type: 实体类型
            slot_index: 槽位索引

        Returns:
            识别结果或 None
        """
        base_region = base_region or UIRegion(
            name=f"{region.name}_base",
            x=region.x,
            y=region.y,
            width=region.width,
            height=region.height,
        )

        # 裁剪区域（当前尺寸）并归一化到基准 ROI 尺寸
        cropped = screenshot.crop(region.bbox)
        normalized = self._normalize_crop_to_base(cropped, base_region)

        # 1. 尝试模板匹配
        template_result = self._match_template(normalized, entity_type)

        # 2. 尝试 OCR
        ocr_result = self._recognize_ocr(normalized, entity_type)

        # 3. 融合结果
        return self._fuse_results(
            template_result=template_result,
            ocr_result=ocr_result,
            region=region,
            base_region=base_region,
            entity_type=entity_type,
            slot_index=slot_index,
        )

    def _match_template(
        self,
        cropped: Image.Image,
        entity_type: str,
    ) -> tuple[str, float, tuple[int, int, int, int]] | None:
        """
        在裁剪图像中进行模板匹配

        Args:
            cropped: 裁剪的图像
            entity_type: 实体类型

        Returns:
            (实体名, 置信度, bbox) 或 None
        """
        best_match: tuple[str, float, tuple[int, int, int, int]] | None = None
        best_confidence = 0.0

        for entity_name in self.registry.list_entities(entity_type):
            template_path = self.registry.get_template_path(entity_type, entity_name)
            if template_path and template_path.exists():
                # 确保模板已加载
                template_key = template_path.stem
                if template_key not in self.matcher.templates:
                    self.matcher.add_template(str(template_path), template_key)

                # 执行匹配
                match = self.matcher.match(
                    image=cropped,
                    template_name=template_key,
                    threshold=self.template_threshold,
                )

                if match and match.confidence > best_confidence:
                    best_confidence = match.confidence
                    best_match = (entity_name, match.confidence, match.bbox)

        return best_match

    def _recognize_ocr(
        self,
        cropped: Image.Image,
        entity_type: str,
    ) -> tuple[str, float, tuple[int, int, int, int]] | None:
        """
        使用 OCR 识别

        Args:
            cropped: 裁剪的图像
            entity_type: 实体类型

        Returns:
            (实体名, 置信度, bbox) 或 None
        """
        # 执行 OCR
        ocr_results = self.ocr.recognize(cropped)

        if not ocr_results:
            return None

        # 尝试匹配 OCR 结果
        for result in ocr_results:
            if result.confidence < self.ocr_confidence_threshold:
                continue

            # 先精确匹配
            entity_name = self.registry.lookup_by_ocr_text(result.text)
            if entity_name:
                return (entity_name, result.confidence, result.bbox)

            # 再模糊匹配
            entity_name = self.registry.lookup_by_ocr_text_fuzzy(result.text, threshold=0.7)
            if entity_name:
                return (entity_name, result.confidence * 0.9, result.bbox)

        return None

    def _fuse_results(
        self,
        template_result: tuple[str, float, tuple[int, int, int, int]] | None,
        ocr_result: tuple[str, float, tuple[int, int, int, int]] | None,
        region: UIRegion,
        entity_type: str,
        slot_index: int | None,
        base_region: UIRegion | None = None,
    ) -> RecognizedEntity | None:
        """
        融合模板匹配和 OCR 结果

        Args:
            template_result: 模板匹配结果
            ocr_result: OCR 结果
            region: 区域
            entity_type: 实体类型
            slot_index: 槽位索引

        Returns:
            融合后的识别结果
        """
        base_region = base_region or region

        # 只有 OCR 结果
        if template_result is None and ocr_result is not None:
            name, conf, local_bbox = ocr_result
            global_bbox = self._map_local_bbox_to_global(local_bbox, region, base_region)
            return RecognizedEntity(
                entity_type=entity_type,
                entity_name=name,
                confidence=conf,
                method="ocr",
                bbox=global_bbox,
                slot_index=slot_index,
            )

        # 只有模板匹配结果
        if template_result is not None and ocr_result is None:
            name, conf, local_bbox = template_result
            global_bbox = self._map_local_bbox_to_global(local_bbox, region, base_region)
            return RecognizedEntity(
                entity_type=entity_type,
                entity_name=name,
                confidence=conf,
                method="template",
                bbox=global_bbox,
                slot_index=slot_index,
            )

        # 两种结果都有
        if template_result is not None and ocr_result is not None:
            t_name, t_conf, t_bbox = template_result
            o_name, o_conf, o_bbox = ocr_result

            # 如果两者识别出相同的实体，提高置信度
            if t_name == o_name:
                global_bbox = self._map_local_bbox_to_global(t_bbox, region, base_region)
                return RecognizedEntity(
                    entity_type=entity_type,
                    entity_name=t_name,
                    confidence=min(1.0, (t_conf + o_conf) / 2 + 0.1),
                    method="hybrid",
                    bbox=global_bbox,
                    slot_index=slot_index,
                )

            # 不同实体，选择置信度更高的
            if t_conf >= o_conf:
                global_bbox = self._map_local_bbox_to_global(t_bbox, region, base_region)
                return RecognizedEntity(
                    entity_type=entity_type,
                    entity_name=t_name,
                    confidence=t_conf,
                    method="template",
                    bbox=global_bbox,
                    slot_index=slot_index,
                )
            else:
                global_bbox = self._map_local_bbox_to_global(o_bbox, region, base_region)
                return RecognizedEntity(
                    entity_type=entity_type,
                    entity_name=o_name,
                    confidence=o_conf,
                    method="ocr",
                    bbox=global_bbox,
                    slot_index=slot_index,
                )

        return None

    def get_transform_diagnostics(self) -> dict[str, object]:
        """返回最近一次识别使用的坐标映射诊断信息。"""
        return self.transform.diagnostics()


def create_recognition_engine(
    template_root: Path | None = None,
    game_data_root: Path | None = None,
    scaler: CoordinateScaler | None = None,
) -> RecognitionEngine:
    """
    创建识别引擎的便捷函数

    Args:
        template_root: 模板根目录
        game_data_root: 游戏数据目录
        scaler: 坐标缩放器

    Returns:
        RecognitionEngine 实例
    """
    from core.vision.ocr_engine import OCREngineType

    # 创建注册表
    registry = TemplateRegistry(template_root=template_root)
    registry.load_from_registry_json()
    if len(registry._entries) == 0:
        # 如果没有注册文件，从游戏数据生成
        registry.load_from_game_data(game_data_root)

    # 创建匹配器
    matcher = TemplateMatcher(default_threshold=0.75)

    # 创建 OCR 引擎
    ocr = OCREngine(engine_type=OCREngineType.AUTO)

    return RecognitionEngine(
        registry=registry,
        matcher=matcher,
        ocr=ocr,
        scaler=scaler,
    )

"""
模板注册表

映射游戏实体到模板文件，支持 OCR 变体匹配
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("template_registry")

# 模板根目录
TEMPLATE_ROOT = Path(__file__).parent.parent.parent / "resources" / "templates"


@dataclass
class TemplateEntry:
    """模板条目"""

    entity_type: str  # "hero" / "item" / "synergy"
    entity_id: str  # 游戏数据中的 canonical name (如 "亚索")
    template_path: Path  # 模板图片相对路径
    ocr_variants: list[str] = field(default_factory=list)  # OCR 可能识别到的文本变体

    def get_full_path(self, template_root: Path) -> Path:
        """获取模板完整路径"""
        return template_root / self.template_path


class TemplateRegistry:
    """
    模板注册表

    管理游戏实体与模板的映射关系
    """

    def __init__(self, template_root: Path | None = None):
        """
        初始化注册表

        Args:
            template_root: 模板根目录，默认为 resources/templates
        """
        self.template_root = template_root or TEMPLATE_ROOT

        # 实体名 -> TemplateEntry
        self._entries: dict[str, TemplateEntry] = {}
        # OCR 文本 -> 实体名 (用于 OCR 变体查询)
        self._ocr_index: dict[str, str] = {}
        # 实体类型 -> 实体名列表
        self._by_type: dict[str, list[str]] = {"hero": [], "item": [], "synergy": []}

    def register(self, entry: TemplateEntry) -> None:
        """
        注册模板条目

        Args:
            entry: 模板条目
        """
        key = f"{entry.entity_type}:{entry.entity_id}"
        self._entries[key] = entry

        # 更新类型索引
        if entry.entity_type not in self._by_type:
            self._by_type[entry.entity_type] = []
        self._by_type[entry.entity_type].append(entry.entity_id)

        # 更新 OCR 索引
        for variant in entry.ocr_variants:
            normalized = self._normalize_text(variant)
            if normalized:
                self._ocr_index[normalized] = entry.entity_id

        logger.debug(f"注册模板: {key} -> {entry.template_path}")

    def get_template_path(self, entity_type: str, entity_name: str) -> Path | None:
        """
        获取实体对应的模板路径

        Args:
            entity_type: 实体类型 (hero/item/synergy)
            entity_name: 实体名称

        Returns:
            模板完整路径或 None
        """
        key = f"{entity_type}:{entity_name}"
        entry = self._entries.get(key)
        if entry:
            return entry.get_full_path(self.template_root)
        return None

    def get_entry(self, entity_type: str, entity_name: str) -> TemplateEntry | None:
        """
        获取模板条目

        Args:
            entity_type: 实体类型
            entity_name: 实体名称

        Returns:
            TemplateEntry 或 None
        """
        key = f"{entity_type}:{entity_name}"
        return self._entries.get(key)

    def lookup_by_ocr_text(self, text: str) -> str | None:
        """
        通过 OCR 文本查找实体名

        Args:
            text: OCR 识别的文本

        Returns:
            实体名称或 None
        """
        normalized = self._normalize_text(text)
        return self._ocr_index.get(normalized)

    def lookup_by_ocr_text_fuzzy(self, text: str, threshold: float = 0.8) -> str | None:
        """
        通过 OCR 文本模糊查找实体名

        Args:
            text: OCR 识别的文本
            threshold: 相似度阈值

        Returns:
            实体名称或 None
        """
        normalized = self._normalize_text(text)

        # 精确匹配
        if normalized in self._ocr_index:
            return self._ocr_index[normalized]

        # 模糊匹配
        best_match: str | None = None
        best_score = 0.0

        for ocr_text, entity_name in self._ocr_index.items():
            score = self._similarity(normalized, ocr_text)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = entity_name

        return best_match

    def list_entities(self, entity_type: str) -> list[str]:
        """
        列出指定类型的所有实体

        Args:
            entity_type: 实体类型

        Returns:
            实体名称列表
        """
        return self._by_type.get(entity_type, []).copy()

    def load_from_registry_json(self, registry_path: Path | None = None) -> int:
        """
        从 registry.json 加载模板注册

        Args:
            registry_path: 注册文件路径，默认为 templates/registry.json

        Returns:
            加载的条目数
        """
        if registry_path is None:
            registry_path = self.template_root / "registry.json"

        if not registry_path.exists():
            logger.warning(f"注册文件不存在: {registry_path}")
            return 0

        try:
            with open(registry_path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"解析注册文件失败: {e}")
            return 0

        count = 0

        # 加载英雄模板
        for name, info in data.get("heroes", {}).items():
            entry = TemplateEntry(
                entity_type="hero",
                entity_id=name,
                template_path=Path(info.get("template", "")),
                ocr_variants=info.get("ocr_variants", [name]),
            )
            self.register(entry)
            count += 1

        # 加载装备模板
        for name, info in data.get("items", {}).items():
            entry = TemplateEntry(
                entity_type="item",
                entity_id=name,
                template_path=Path(info.get("template", "")),
                ocr_variants=info.get("ocr_variants", [name]),
            )
            self.register(entry)
            count += 1

        # 加载羁绊模板
        for name, info in data.get("synergies", {}).items():
            entry = TemplateEntry(
                entity_type="synergy",
                entity_id=name,
                template_path=Path(info.get("template", "")),
                ocr_variants=info.get("ocr_variants", [name]),
            )
            self.register(entry)
            count += 1

        logger.info(f"从 {registry_path} 加载了 {count} 个模板条目")
        return count

    def load_from_game_data(self, game_data_root: Path | None = None) -> int:
        """
        从游戏数据自动生成模板注册

        Args:
            game_data_root: 游戏数据目录，默认为 resources/game_data

        Returns:
            生成的条目数
        """
        if game_data_root is None:
            game_data_root = self.template_root.parent / "game_data"

        count = 0

        # 加载英雄
        heroes_file = game_data_root / "heroes.json"
        if heroes_file.exists():
            try:
                with open(heroes_file, encoding="utf-8") as f:
                    data = json.load(f)
                for hero in data.get("heroes", []):
                    name = hero["name"]
                    cost = hero["cost"]
                    # 根据费用确定模板路径
                    template_path = Path(f"heroes/cost{cost}/{self._name_to_filename(name)}.png")
                    entry = TemplateEntry(
                        entity_type="hero",
                        entity_id=name,
                        template_path=template_path,
                        ocr_variants=[name],
                    )
                    self.register(entry)
                    count += 1
            except Exception as e:
                logger.error(f"加载英雄数据失败: {e}")

        # 加载装备
        items_file = game_data_root / "items.json"
        if items_file.exists():
            try:
                with open(items_file, encoding="utf-8") as f:
                    data = json.load(f)

                # 基础装备
                for item in data.get("base_items", []):
                    name = item["name"]
                    template_path = Path(f"items/base/{self._name_to_filename(name)}.png")
                    entry = TemplateEntry(
                        entity_type="item",
                        entity_id=name,
                        template_path=template_path,
                        ocr_variants=[name],
                    )
                    self.register(entry)
                    count += 1

                # 合成装备
                for item in data.get("combined_items", []):
                    name = item["name"]
                    template_path = Path(f"items/combined/{self._name_to_filename(name)}.png")
                    entry = TemplateEntry(
                        entity_type="item",
                        entity_id=name,
                        template_path=template_path,
                        ocr_variants=[name],
                    )
                    self.register(entry)
                    count += 1
            except Exception as e:
                logger.error(f"加载装备数据失败: {e}")

        # 加载羁绊
        synergies_file = game_data_root / "synergies.json"
        if synergies_file.exists():
            try:
                with open(synergies_file, encoding="utf-8") as f:
                    data = json.load(f)
                for name in data.get("synergies", {}).keys():
                    template_path = Path(f"synergies/{self._name_to_filename(name)}.png")
                    entry = TemplateEntry(
                        entity_type="synergy",
                        entity_id=name,
                        template_path=template_path,
                        ocr_variants=[name],
                    )
                    self.register(entry)
                    count += 1
            except Exception as e:
                logger.error(f"加载羁绊数据失败: {e}")

        logger.info(f"从游戏数据生成了 {count} 个模板条目")
        return count

    def save_registry_json(self, registry_path: Path | None = None) -> bool:
        """
        保存注册表到 JSON 文件

        Args:
            registry_path: 目标路径

        Returns:
            是否成功
        """
        if registry_path is None:
            registry_path = self.template_root / "registry.json"

        data: dict[str, Any] = {
            "version": "S13",
            "heroes": {},
            "items": {},
            "synergies": {},
        }

        for key, entry in self._entries.items():
            entity_data = {
                "template": str(entry.template_path),
                "ocr_variants": entry.ocr_variants,
            }

            if entry.entity_type == "hero":
                data["heroes"][entry.entity_id] = entity_data
            elif entry.entity_type == "item":
                data["items"][entry.entity_id] = entity_data
            elif entry.entity_type == "synergy":
                data["synergies"][entry.entity_id] = entity_data

        try:
            registry_path.parent.mkdir(parents=True, exist_ok=True)
            with open(registry_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"保存注册表到 {registry_path}")
            return True
        except Exception as e:
            logger.error(f"保存注册表失败: {e}")
            return False

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "total_entries": len(self._entries),
            "by_type": {t: len(v) for t, v in self._by_type.items()},
            "ocr_index_size": len(self._ocr_index),
            "template_root": str(self.template_root),
        }

    def validate_templates(self) -> dict[str, Any]:
        """
        校验所有注册的模板文件是否存在

        Returns:
            校验结果，包含 missing (缺失列表), existing (存在列表), stats (统计)
        """
        missing: list[dict[str, str]] = []
        existing: list[dict[str, str]] = []

        for key, entry in self._entries.items():
            full_path = entry.get_full_path(self.template_root)
            if full_path.exists():
                existing.append(
                    {
                        "entity_type": entry.entity_type,
                        "entity_id": entry.entity_id,
                        "path": str(entry.template_path),
                    }
                )
            else:
                missing.append(
                    {
                        "entity_type": entry.entity_type,
                        "entity_id": entry.entity_id,
                        "path": str(entry.template_path),
                    }
                )

        return {
            "missing": missing,
            "existing": existing,
            "stats": {
                "total": len(self._entries),
                "missing_count": len(missing),
                "existing_count": len(existing),
                "missing_by_type": self._count_by_type(missing),
            },
        }

    def _count_by_type(self, items: list[dict[str, str]]) -> dict[str, int]:
        """按类型统计"""
        counts: dict[str, int] = {}
        for item in items:
            t = item["entity_type"]
            counts[t] = counts.get(t, 0) + 1
        return counts

    def check_template_exists(self, entity_type: str, entity_name: str) -> bool:
        """
        检查单个模板是否存在

        Args:
            entity_type: 实体类型
            entity_name: 实体名称

        Returns:
            是否存在
        """
        path = self.get_template_path(entity_type, entity_name)
        return path is not None and path.exists()

    def get_missing_templates_message(self) -> str | None:
        """
        获取缺失模板的可读报错信息

        Returns:
            报错信息字符串，如果没有缺失则返回 None
        """
        result = self.validate_templates()
        missing = result["missing"]

        if not missing:
            return None

        lines = [f"⚠️ 缺失 {len(missing)} 个模板文件:"]

        # 按类型分组
        by_type: dict[str, list[dict[str, str]]] = {}
        for item in missing:
            t = item["entity_type"]
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(item)

        for entity_type, items in by_type.items():
            lines.append(f"\n[{entity_type}] {len(items)} 个:")
            for item in items[:5]:  # 只显示前5个
                lines.append(f"  - {item['entity_id']}: {item['path']}")
            if len(items) > 5:
                lines.append(f"  ... 还有 {len(items) - 5} 个")

        lines.append(f"\n模板根目录: {self.template_root}")
        lines.append("请检查模板文件是否已导入到正确位置")

        return "\n".join(lines)

    def count_s13_imported(self) -> int:
        """
        统计 s13_imported 目录中的模板数量

        Returns:
            模板数量
        """
        s13_dir = self.template_root / "s13_imported"
        if not s13_dir.exists():
            return 0
        return len(list(s13_dir.glob("*.png")))

    @staticmethod
    def _normalize_text(text: str) -> str:
        """规范化文本（去除空格、转小写）"""
        return text.strip().lower()

    @staticmethod
    def _name_to_filename(name: str) -> str:
        """将中文名转换为文件名（使用拼音或英文）"""
        # 简单实现：直接使用中文名
        # 实际项目中可以使用拼音转换库
        return name

    @staticmethod
    def _similarity(s1: str, s2: str) -> float:
        """
        计算两个字符串的相似度（简单实现）

        使用编辑距离的简化版本
        """
        if not s1 or not s2:
            return 0.0

        if s1 == s2:
            return 1.0

        # 使用 Levenshtein 距离的简化版本
        len1, len2 = len(s1), len(s2)

        # 简单实现：计算公共字符比例
        common = sum(1 for c in s1 if c in s2)
        return common / max(len1, len2)

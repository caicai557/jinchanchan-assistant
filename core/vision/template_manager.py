"""
模板管理器

管理游戏 UI 元素模板，支持模板匹配
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

logger = logging.getLogger("template_manager")

# 模板根目录
TEMPLATE_ROOT = Path(__file__).parent.parent.parent / "resources" / "templates"


@dataclass
class TemplateMatch:
    """模板匹配结果"""

    template_name: str
    category: str
    x: int
    y: int
    width: int
    height: int
    confidence: float


class TemplateManager:
    """
    模板管理器

    加载和管理 UI 元素模板，提供模板匹配功能
    """

    def __init__(self, template_root: Path | None = None):
        """
        初始化模板管理器

        Args:
            template_root: 模板根目录，默认为 resources/templates
        """
        self.template_root = template_root or TEMPLATE_ROOT
        self._templates: dict[str, dict[str, Image.Image]] = {}
        self._load_templates()

    def _load_templates(self) -> None:
        """加载所有模板"""
        if not self.template_root.exists():
            logger.warning(f"模板目录不存在: {self.template_root}")
            return

        categories = ["buttons", "heroes", "items", "status"]
        total = 0

        for category in categories:
            category_dir = self.template_root / category
            if not category_dir.exists():
                continue

            self._templates[category] = {}

            for template_file in category_dir.glob("*.png"):
                try:
                    img = Image.open(template_file)
                    template_name = template_file.stem
                    self._templates[category][template_name] = img
                    total += 1
                except Exception as e:
                    logger.warning(f"加载模板失败 {template_file}: {e}")

        logger.info(f"加载了 {total} 个模板")

    def get_template(self, category: str, name: str) -> Image.Image | None:
        """
        获取指定模板

        Args:
            category: 模板类别 (buttons/heroes/items/status)
            name: 模板名称 (不含扩展名)

        Returns:
            PIL Image 或 None
        """
        return self._templates.get(category, {}).get(name)

    def list_templates(self, category: str | None = None) -> dict[str, list[str]]:
        """
        列出模板

        Args:
            category: 指定类别，None 则列出所有

        Returns:
            {category: [template_names]}
        """
        if category:
            return {category: list(self._templates.get(category, {}).keys())}
        return {cat: list(templates.keys()) for cat, templates in self._templates.items()}

    def match(
        self,
        screenshot: Image.Image,
        category: str | None = None,
        threshold: float = 0.8,
    ) -> list[TemplateMatch]:
        """
        在截图中匹配模板

        Args:
            screenshot: 游戏截图
            category: 限定类别，None 则搜索所有
            threshold: 匹配置信度阈值

        Returns:
            匹配结果列表
        """
        matches: list[TemplateMatch] = []

        try:
            import cv2
            import numpy as np
        except ImportError:
            logger.warning("OpenCV 未安装，无法进行模板匹配")
            return matches

        # 转换截图为 OpenCV 格式
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        categories = [category] if category else list(self._templates.keys())

        for cat in categories:
            for name, template in self._templates.get(cat, {}).items():
                template_cv = cv2.cvtColor(np.array(template), cv2.COLOR_RGB2BGR)

                # 模板匹配
                result = cv2.matchTemplate(screenshot_cv, template_cv, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

                if max_val >= threshold:
                    h, w = template_cv.shape[:2]
                    matches.append(
                        TemplateMatch(
                            template_name=name,
                            category=cat,
                            x=int(max_loc[0]),
                            y=int(max_loc[1]),
                            width=w,
                            height=h,
                            confidence=float(max_val),
                        )
                    )

        # 按置信度排序
        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches

    def find_button(self, screenshot: Image.Image, button_name: str) -> TemplateMatch | None:
        """
        查找指定按钮

        Args:
            screenshot: 游戏截图
            button_name: 按钮名称

        Returns:
            最佳匹配或 None
        """
        matches = self.match(screenshot, category="buttons", threshold=0.7)
        for m in matches:
            if m.template_name == button_name:
                return m
        return None

    def find_all_buttons(self, screenshot: Image.Image) -> list[TemplateMatch]:
        """查找所有按钮"""
        return self.match(screenshot, category="buttons", threshold=0.7)

    def get_stats(self) -> dict[str, Any]:
        """获取模板统计信息"""
        return {
            "total_templates": sum(len(t) for t in self._templates.values()),
            "categories": {cat: len(templates) for cat, templates in self._templates.items()},
            "template_root": str(self.template_root),
        }

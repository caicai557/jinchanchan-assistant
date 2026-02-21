"""
SoM (Set-of-Mark) 标注器

在截图上添加编号标记，帮助 VLM 精确定位
"""

from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageDraw, ImageFont


@dataclass
class Region:
    """标注区域"""

    id: int
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    label: str | None = None
    color: str = "red"
    metadata: dict[str, Any] | None = None

    @property
    def center(self) -> tuple[int, int]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    @property
    def width(self) -> int:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> int:
        return self.bbox[3] - self.bbox[1]


class SoMAnnotator:
    """
    Set-of-Mark 标注器

    在游戏截图上添加编号标记，帮助 VLM 理解和定位元素
    """

    # 预定义颜色
    COLORS = {
        "red": "#FF0000",
        "green": "#00FF00",
        "blue": "#0000FF",
        "yellow": "#FFFF00",
        "cyan": "#00FFFF",
        "magenta": "#FF00FF",
        "orange": "#FFA500",
        "white": "#FFFFFF",
    }

    def __init__(self, font_size: int = 14, box_width: int = 2, show_labels: bool = True):
        """
        初始化标注器

        Args:
            font_size: 标签字体大小
            box_width: 边框宽度
            show_labels: 是否显示标签文字
        """
        self.font_size = font_size
        self.box_width = box_width
        self.show_labels = show_labels
        # Union type for font: can be FreeTypeFont or basic ImageFont
        self._font: ImageFont.FreeTypeFont | ImageFont.ImageFont | None = None

    def annotate(
        self,
        image: Image.Image,
        regions: list[Region],
        show_ids: bool = True,
        show_bboxes: bool = True,
    ) -> Image.Image:
        """
        在图像上添加标注

        Args:
            image: 原始图像
            regions: 标注区域列表
            show_ids: 是否显示编号
            show_bboxes: 是否显示边界框

        Returns:
            标注后的图像
        """
        # 复制图像
        annotated = image.copy()
        draw = ImageDraw.Draw(annotated)

        # 加载字体
        font = self._get_font()

        for region in regions:
            x1, y1, x2, y2 = region.bbox
            color = self.COLORS.get(region.color, region.color)

            # 绘制边界框
            if show_bboxes:
                draw.rectangle((x1, y1, x2, y2), outline=color, width=self.box_width)

            # 绘制编号
            if show_ids:
                # 背景框
                text = f"#{region.id}"
                if self.show_labels and region.label:
                    text += f" {region.label}"

                # 计算文本大小
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]

                # 绘制背景
                label_y = max(0, y1 - text_height - 4)
                draw.rectangle(
                    (x1, label_y, x1 + text_width + 4, label_y + text_height + 2), fill=color
                )

                # 绘制文本
                draw.text(
                    (x1 + 2, label_y + 1),
                    text,
                    fill="white" if color != "#FFFFFF" else "black",
                    font=font,
                )

        return annotated

    def annotate_grid(
        self,
        image: Image.Image,
        rows: int,
        cols: int,
        start_id: int = 1,
        labels: list[list[str]] | None = None,
    ) -> tuple[Image.Image, list[Region]]:
        """
        添加网格标注（用于棋盘等区域）

        Args:
            image: 原始图像
            rows: 行数
            cols: 列数
            start_id: 起始编号
            labels: 标签矩阵 [rows][cols]

        Returns:
            标注后的图像和区域列表
        """
        width, height = image.size
        cell_width = width // cols
        cell_height = height // rows

        regions = []
        region_id = start_id

        for row in range(rows):
            for col in range(cols):
                x1 = col * cell_width
                y1 = row * cell_height
                x2 = x1 + cell_width
                y2 = y1 + cell_height

                label = None
                if labels and row < len(labels) and col < len(labels[row]):
                    label = labels[row][col]

                regions.append(Region(id=region_id, bbox=(x1, y1, x2, y2), label=label))
                region_id += 1

        annotated = self.annotate(image, regions)
        return annotated, regions

    def create_shop_annotation(
        self, image: Image.Image, shop_slots: int = 5
    ) -> tuple[Image.Image, list[Region]]:
        """
        创建商店区域标注

        Args:
            image: 原始图像
            shop_slots: 商店槽位数量

        Returns:
            标注后的图像和区域列表
        """
        width, height = image.size

        # 商店通常在屏幕底部，占据一定高度
        # 这里使用启发式值，实际应根据游戏分辨率调整
        shop_height = int(height * 0.1)
        shop_top = height - shop_height - int(height * 0.05)

        slot_width = width // shop_slots

        regions = []
        for i in range(shop_slots):
            x1 = i * slot_width
            x2 = x1 + slot_width
            y1 = shop_top
            y2 = shop_top + shop_height

            regions.append(
                Region(id=i + 1, bbox=(x1, y1, x2, y2), label=f"商店{i + 1}", color="yellow")
            )

        annotated = self.annotate(image, regions)
        return annotated, regions

    def create_board_annotation(
        self, image: Image.Image, board_rows: int = 4, board_cols: int = 7
    ) -> tuple[Image.Image, list[Region]]:
        """
        创建棋盘区域标注

        Args:
            image: 原始图像
            board_rows: 棋盘行数
            board_cols: 棋盘列数

        Returns:
            标注后的图像和区域列表
        """
        width, height = image.size

        # 棋盘区域（启发式）
        board_width = int(width * 0.7)
        board_height = int(height * 0.35)
        board_left = (width - board_width) // 2
        board_top = int(height * 0.45)

        cell_width = board_width // board_cols
        cell_height = board_height // board_rows

        regions = []
        region_id = 1

        for row in range(board_rows):
            for col in range(board_cols):
                x1 = board_left + col * cell_width
                y1 = board_top + row * cell_height
                x2 = x1 + cell_width
                y2 = y1 + cell_height

                regions.append(
                    Region(
                        id=region_id, bbox=(x1, y1, x2, y2), label=f"({row},{col})", color="green"
                    )
                )
                region_id += 1

        annotated = self.annotate(image, regions)
        return annotated, regions

    def create_full_annotation(
        self, image: Image.Image
    ) -> tuple[Image.Image, dict[str, list[Region]]]:
        """
        创建完整游戏界面的标注

        Args:
            image: 原始图像

        Returns:
            标注后的图像和区域字典
        """
        width, height = image.size
        all_regions: dict[str, list[Region]] = {}
        all_region_list: list[Region] = []
        current_id = 1

        # 创建标注副本
        annotated = image.copy()

        # 1. 金币区域（右上）
        gold_region = Region(
            id=current_id, bbox=(width - 150, 10, width - 50, 40), label="金币", color="yellow"
        )
        all_regions["gold"] = [gold_region]
        all_region_list.append(gold_region)
        current_id += 1

        # 2. 血量区域（右上偏下）
        hp_region = Region(
            id=current_id, bbox=(width - 150, 50, width - 50, 80), label="血量", color="red"
        )
        all_regions["hp"] = [hp_region]
        all_region_list.append(hp_region)
        current_id += 1

        # 3. 等级区域
        level_region = Region(
            id=current_id, bbox=(width - 150, 90, width - 50, 120), label="等级", color="blue"
        )
        all_regions["level"] = [level_region]
        all_region_list.append(level_region)
        current_id += 1

        # 4. 商店槽位
        shop_regions = []
        shop_height = int(height * 0.1)
        shop_top = height - shop_height - int(height * 0.05)
        slot_width = width // 5

        for i in range(5):
            x1 = i * slot_width
            shop_regions.append(
                Region(
                    id=current_id,
                    bbox=(x1, shop_top, x1 + slot_width, shop_top + shop_height),
                    label=f"商店{i + 1}",
                    color="yellow",
                )
            )
            current_id += 1

        all_regions["shop"] = shop_regions
        all_region_list.extend(shop_regions)

        # 5. 棋盘区域
        board_regions = []
        board_width = int(width * 0.7)
        board_height = int(height * 0.35)
        board_left = (width - board_width) // 2
        board_top = int(height * 0.45)
        cell_width = board_width // 7
        cell_height = board_height // 4

        for row in range(4):
            for col in range(7):
                x1 = board_left + col * cell_width
                y1 = board_top + row * cell_height
                board_regions.append(
                    Region(
                        id=current_id,
                        bbox=(x1, y1, x1 + cell_width, y1 + cell_height),
                        label=f"({row},{col})",
                        color="green",
                    )
                )
                current_id += 1

        all_regions["board"] = board_regions
        all_region_list.extend(board_regions)

        # 应用所有标注
        draw = ImageDraw.Draw(annotated)
        font = self._get_font()

        for region in all_region_list:
            x1, y1, x2, y2 = region.bbox
            color = self.COLORS.get(region.color, region.color)

            # 绘制边界框
            draw.rectangle((x1, y1, x2, y2), outline=color, width=self.box_width)

            # 绘制编号
            text = f"#{region.id}"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            label_y = max(0, y1 - text_height - 4)
            draw.rectangle(
                (x1, label_y, x1 + text_width + 4, label_y + text_height + 2), fill=color
            )
            draw.text((x1 + 2, label_y + 1), text, fill="white", font=font)

        return annotated, all_regions

    def _get_font(self) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """获取字体"""
        if self._font is not None:
            return self._font

        # 尝试加载系统字体
        font_paths = [
            "/System/Library/Fonts/PingFang.ttc",  # macOS
            "/System/Library/Fonts/STHeiti Light.ttc",  # macOS 备选
            "C:\\Windows\\Fonts\\msyh.ttc",  # Windows
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",  # Linux
        ]

        for path in font_paths:
            try:
                font = ImageFont.truetype(path, self.font_size)
                self._font = font
                return font
            except Exception:
                continue

        # 使用默认字体
        default_font: ImageFont.FreeTypeFont | ImageFont.ImageFont = ImageFont.load_default()
        self._font = default_font
        return default_font

    def regions_to_description(self, regions: list[Region]) -> str:
        """
        将区域列表转换为文本描述

        Args:
            regions: 区域列表

        Returns:
            文本描述
        """
        lines = ["标注区域说明："]
        for region in regions:
            label = region.label or "未命名"
            lines.append(f"  #{region.id}: {label} - 位置 ({region.center[0]}, {region.center[1]})")

        return "\n".join(lines)

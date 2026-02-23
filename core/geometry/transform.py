"""统一坐标映射层。"""

from __future__ import annotations

from dataclasses import dataclass

Size2D = tuple[int, int]
RectXYWH = tuple[int, int, int, int]


def _validate_size(size: Size2D, name: str) -> None:
    w, h = size
    if w <= 0 or h <= 0:
        raise ValueError(f"{name} 必须为正数，当前: {size}")


def infer_letterbox_content_rect(base_size: Size2D, current_size: Size2D) -> RectXYWH:
    """按基准宽高比在当前窗口中推断内容区（居中 letterbox）。"""
    _validate_size(base_size, "base_size")
    _validate_size(current_size, "current_size")

    base_w, base_h = base_size
    cur_w, cur_h = current_size

    scale = min(cur_w / base_w, cur_h / base_h)
    content_w = max(1, int(base_w * scale))
    content_h = max(1, int(base_h * scale))
    offset_x = max(0, (cur_w - content_w) // 2)
    offset_y = max(0, (cur_h - content_h) // 2)
    return (offset_x, offset_y, content_w, content_h)


@dataclass(frozen=True)
class CoordinateTransform:
    """
    基于基准分辨率的统一坐标映射。

    - `base_size`: regions 定义使用的基准分辨率（如 1920x1080）
    - `current_size`: 当前窗口截图尺寸
    - `content_rect`: 当前截图中的实际游戏内容区 `(x, y, w, h)`，可用于 letterbox
    """

    base_size: Size2D
    current_size: Size2D
    content_rect: RectXYWH | None = None

    def __post_init__(self) -> None:
        _validate_size(self.base_size, "base_size")
        _validate_size(self.current_size, "current_size")

        rect = self.content_rect
        if rect is None:
            rect = infer_letterbox_content_rect(self.base_size, self.current_size)

        x, y, w, h = rect
        if x < 0 or y < 0 or w <= 0 or h <= 0:
            raise ValueError(f"content_rect 非法: {rect}")

        cur_w, cur_h = self.current_size
        if x + w > cur_w or y + h > cur_h:
            raise ValueError(f"content_rect 越界: rect={rect}, current_size={self.current_size}")

        object.__setattr__(self, "content_rect", rect)

    @property
    def scale(self) -> tuple[float, float]:
        """返回 `(scale_x, scale_y)`。"""
        _, _, content_w, content_h = self.content_rect_or_full()
        base_w, base_h = self.base_size
        return (content_w / base_w, content_h / base_h)

    @property
    def offset(self) -> tuple[int, int]:
        """返回 `(offset_x, offset_y)`。"""
        x, y, _, _ = self.content_rect_or_full()
        return (x, y)

    @property
    def scale_x(self) -> float:
        return self.scale[0]

    @property
    def scale_y(self) -> float:
        return self.scale[1]

    @property
    def offset_x(self) -> int:
        return self.offset[0]

    @property
    def offset_y(self) -> int:
        return self.offset[1]

    def content_rect_or_full(self) -> RectXYWH:
        rect = self.content_rect
        if rect is None:
            return (0, 0, self.current_size[0], self.current_size[1])
        return rect

    def map_point(self, x: int | tuple[int, int], y: int | None = None) -> tuple[int, int]:
        """将基准坐标点映射到当前坐标。"""
        if isinstance(x, tuple):
            bx, by = x
        else:
            if y is None:
                raise ValueError("map_point 需要 x,y")
            bx, by = x, y

        ox, oy = self.offset
        sx, sy = self.scale
        return (int(ox + bx * sx), int(oy + by * sy))

    def map_size(self, width: int, height: int) -> tuple[int, int]:
        """将基准尺寸映射到当前尺寸。"""
        sx, sy = self.scale
        return (max(1, int(width * sx)), max(1, int(height * sy)))

    def map_rect(
        self,
        rect_or_x: RectXYWH | int,
        y: int | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> RectXYWH:
        """将基准矩形 `(x, y, w, h)` 映射到当前坐标。"""
        if isinstance(rect_or_x, tuple):
            bx, by, bw, bh = rect_or_x
        else:
            if y is None or width is None or height is None:
                raise ValueError("map_rect 需要 x,y,width,height")
            bx, by, bw, bh = rect_or_x, y, width, height

        x1, y1 = self.map_point(bx, by)
        w2, h2 = self.map_size(bw, bh)
        return (x1, y1, w2, h2)

    def map_bbox(self, bbox: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        """将基准 bbox `(x1, y1, x2, y2)` 映射到当前坐标。"""
        x1, y1 = self.map_point((bbox[0], bbox[1]))
        x2, y2 = self.map_point((bbox[2], bbox[3]))
        return (x1, y1, x2, y2)

    def unmap_point(self, x: int | tuple[int, int], y: int | None = None) -> tuple[int, int]:
        """将当前坐标点映射回基准坐标。"""
        if isinstance(x, tuple):
            cx, cy = x
        else:
            if y is None:
                raise ValueError("unmap_point 需要 x,y")
            cx, cy = x, y

        ox, oy = self.offset
        sx, sy = self.scale
        if sx == 0 or sy == 0:
            raise ZeroDivisionError("缩放系数为 0，无法反向映射")
        return (int((cx - ox) / sx), int((cy - oy) / sy))

    def with_content_rect(self, content_rect: RectXYWH | None) -> CoordinateTransform:
        """返回一个替换 content_rect 后的新实例。"""
        return CoordinateTransform(
            base_size=self.base_size,
            current_size=self.current_size,
            content_rect=content_rect,
        )

    def diagnostics(self) -> dict[str, object]:
        """便于日志/doctor 输出的诊断信息。"""
        return {
            "base_size": self.base_size,
            "current_size": self.current_size,
            "content_rect": self.content_rect_or_full(),
            "scale": self.scale,
            "offset": self.offset,
        }

"""
坐标缩放器

支持多分辨率适配，基于参考分辨率动态缩放坐标
"""

from dataclasses import dataclass


@dataclass
class Resolution:
    """分辨率定义"""

    width: int
    height: int

    @classmethod
    def HD_1080(cls) -> "Resolution":
        """1920x1080 (参考分辨率)"""
        return cls(1920, 1080)

    @classmethod
    def from_tuple(cls, size: tuple[int, int]) -> "Resolution":
        return cls(size[0], size[1])

    def aspect_ratio(self) -> float:
        return self.width / self.height


class CoordinateScaler:
    """
    坐标缩放器

    将参考分辨率 (1920x1080) 的坐标缩放到目标分辨率
    """

    # 参考分辨率 (金铲铲之战标准分辨率)
    REFERENCE = Resolution.HD_1080()

    def __init__(self, target: Resolution | None = None):
        """
        初始化缩放器

        Args:
            target: 目标分辨率，None 时使用参考分辨率
        """
        self.target = target or self.REFERENCE
        self._scale_x = self.target.width / self.REFERENCE.width
        self._scale_y = self.target.height / self.REFERENCE.height

    @classmethod
    def from_window_size(cls, width: int, height: int) -> "CoordinateScaler":
        """从窗口尺寸创建缩放器"""
        return cls(Resolution(width, height))

    def scale_point(self, x: int, y: int) -> tuple[int, int]:
        """
        缩放单点坐标

        Args:
            x: 参考分辨率下的 X 坐标
            y: 参考分辨率下的 Y 坐标

        Returns:
            目标分辨率下的 (x, y)
        """
        return (int(x * self._scale_x), int(y * self._scale_y))

    def scale_size(self, width: int, height: int) -> tuple[int, int]:
        """
        缩放尺寸

        Args:
            width: 参考分辨率下的宽度
            height: 参考分辨率下的高度

        Returns:
            目标分辨率下的 (width, height)
        """
        return (int(width * self._scale_x), int(height * self._scale_y))

    def scale_rect(self, x: int, y: int, width: int, height: int) -> tuple[int, int, int, int]:
        """
        缩放矩形区域

        Args:
            x, y: 左上角坐标
            width, height: 尺寸

        Returns:
            目标分辨率下的 (x, y, width, height)
        """
        sx, sy = self.scale_point(x, y)
        sw, sh = self.scale_size(width, height)
        return (sx, sy, sw, sh)

    def scale_points(self, points: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """
        批量缩放点坐标

        Args:
            points: 参考分辨率下的点列表

        Returns:
            目标分辨率下的点列表
        """
        return [self.scale_point(x, y) for x, y in points]

    @property
    def scale_factor(self) -> tuple[float, float]:
        """返回 (scale_x, scale_y)"""
        return (self._scale_x, self._scale_y)

    def is_reference(self) -> bool:
        """是否为参考分辨率"""
        return self.target.width == self.REFERENCE.width and (
            self.target.height == self.REFERENCE.height
        )


# 预定义分辨率配置
RESOLUTION_CONFIGS = {
    "1080p": Resolution(1920, 1080),
    "2k": Resolution(2560, 1440),
    "4k": Resolution(3840, 2160),
    # 模拟器常见分辨率
    "mac_retina": Resolution(3096, 2064),  # S13 福星版本分辨率
    "simulator_hd": Resolution(1280, 720),
}


def get_scaler_for_resolution(width: int, height: int) -> CoordinateScaler:
    """
    获取指定分辨率的缩放器

    Args:
        width: 窗口宽度
        height: 窗口高度

    Returns:
        CoordinateScaler 实例
    """
    return CoordinateScaler.from_window_size(width, height)

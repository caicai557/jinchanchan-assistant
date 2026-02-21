"""
平台适配器协议 - 定义所有平台必须实现的接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

from PIL import Image


@dataclass
class WindowInfo:
    """窗口信息"""

    title: str
    left: int
    top: int
    width: int
    height: int
    window_id: int | None = None

    @property
    def rect(self) -> tuple[int, int, int, int]:
        """返回 (left, top, width, height)"""
        return (self.left, self.top, self.width, self.height)

    @property
    def center(self) -> tuple[int, int]:
        """返回窗口中心坐标"""
        return (self.left + self.width // 2, self.top + self.height // 2)


class PlatformAdapter(Protocol):
    """
    平台适配器协议 - 所有平台必须实现此接口

    支持 Mac PlayCover 和 Windows 模拟器两种平台
    """

    def get_screenshot(self) -> Image.Image:
        """
        获取游戏窗口截图

        Returns:
            PIL.Image.Image: 截图图像，RGB 格式
        """
        ...

    def click(
        self, x: int, y: int, button: str = "left", clicks: int = 1, interval: float = 0.1
    ) -> bool:
        """
        点击指定坐标

        Args:
            x: X 坐标（屏幕绝对坐标）
            y: Y 坐标（屏幕绝对坐标）
            button: 鼠标按钮 ("left", "right", "middle")
            clicks: 点击次数
            interval: 多次点击之间的间隔（秒）

        Returns:
            bool: 点击是否成功
        """
        ...

    def drag(
        self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5
    ) -> bool:
        """
        从起点拖动到终点

        Args:
            start_x: 起点X坐标
            start_y: 起点Y坐标
            end_x: 终点X坐标
            end_y: 终点Y坐标
            duration: 拖动持续时间（秒）

        Returns:
            bool: 拖动是否成功
        """
        ...

    def scroll(self, x: int, y: int, clicks: int = 1) -> bool:
        """
        滚动操作

        Args:
            x: X 坐标
            y: Y 坐标
            clicks: 滚动次数，正数向上，负数向下

        Returns:
            bool: 滚动是否成功
        """
        ...

    def type_text(self, text: str, interval: float = 0.05) -> bool:
        """
        输入文本

        Args:
            text: 要输入的文本
            interval: 按键间隔（秒）

        Returns:
            bool: 输入是否成功
        """
        ...

    def press_key(self, key: str) -> bool:
        """
        按下并释放按键

        Args:
            key: 按键名称 (如 "enter", "escape", "space")

        Returns:
            bool: 按键是否成功
        """
        ...

    def get_game_window_rect(self) -> tuple[int, int, int, int]:
        """
        获取游戏窗口位置和大小

        Returns:
            Tuple[int, int, int, int]: (left, top, width, height)
        """
        ...

    def get_window_info(self) -> WindowInfo | None:
        """
        获取窗口详细信息

        Returns:
            WindowInfo 或 None（如果窗口不存在）
        """
        ...

    def is_game_active(self) -> bool:
        """
        检查游戏窗口是否激活（前台）

        Returns:
            bool: 游戏窗口是否激活
        """
        ...

    def activate_game(self) -> bool:
        """
        激活游戏窗口（将其置于前台）

        Returns:
            bool: 是否成功激活
        """
        ...

    def screen_to_window(self, x: int, y: int) -> tuple[int, int]:
        """
        屏幕坐标转换为窗口坐标

        Args:
            x: 屏幕X坐标
            y: 屏幕Y坐标

        Returns:
            Tuple[int, int]: 窗口内坐标
        """
        ...

    def window_to_screen(self, x: int, y: int) -> tuple[int, int]:
        """
        窗口坐标转换为屏幕坐标

        Args:
            x: 窗口内X坐标
            y: 窗口内Y坐标

        Returns:
            Tuple[int, int]: 屏幕坐标
        """
        ...

    def get_scale_factor(self) -> float:
        """
        获取窗口缩放因子（用于 Retina 屏幕等高DPI场景）

        Returns:
            float: 缩放因子（1.0 为标准）
        """
        ...


class BasePlatformAdapter(ABC):
    """
    平台适配器基类 - 提供通用实现

    子类只需实现少量平台特定方法
    """

    def __init__(self, window_title: str = "金铲铲之战"):
        self.window_title = window_title
        self._window_info: WindowInfo | None = None
        self._scale_factor: float | None = None

    @abstractmethod
    def _find_window(self) -> WindowInfo | None:
        """查找游戏窗口（平台特定实现）"""
        pass

    @abstractmethod
    def _capture_impl(self, rect: tuple[int, int, int, int]) -> Image.Image:
        """截图实现（平台特定）"""
        pass

    @abstractmethod
    def _click_impl(self, x: int, y: int, button: str) -> bool:
        """点击实现（平台特定）"""
        pass

    def _refresh_window_info(self) -> WindowInfo | None:
        """刷新窗口信息"""
        self._window_info = self._find_window()
        return self._window_info

    def get_window_info(self) -> WindowInfo | None:
        """获取窗口信息"""
        if self._window_info is None:
            self._refresh_window_info()
        return self._window_info

    def get_game_window_rect(self) -> tuple[int, int, int, int]:
        """获取游戏窗口矩形"""
        info = self.get_window_info()
        if info is None:
            raise RuntimeError(f"未找到游戏窗口: {self.window_title}")
        return info.rect

    def get_screenshot(self) -> Image.Image:
        """获取游戏窗口截图"""
        rect = self.get_game_window_rect()
        return self._capture_impl(rect)

    def click(
        self, x: int, y: int, button: str = "left", clicks: int = 1, interval: float = 0.1
    ) -> bool:
        """点击指定坐标"""
        for _ in range(clicks):
            if not self._click_impl(x, y, button):
                return False
            if clicks > 1:
                import time

                time.sleep(interval)
        return True

    def screen_to_window(self, x: int, y: int) -> tuple[int, int]:
        """屏幕坐标转窗口坐标"""
        rect = self.get_game_window_rect()
        return (x - rect[0], y - rect[1])

    def window_to_screen(self, x: int, y: int) -> tuple[int, int]:
        """窗口坐标转屏幕坐标"""
        rect = self.get_game_window_rect()
        return (x + rect[0], y + rect[1])

    def get_scale_factor(self) -> float:
        """获取缩放因子"""
        if self._scale_factor is None:
            # 默认实现，子类可覆盖
            self._scale_factor = 1.0
        return self._scale_factor

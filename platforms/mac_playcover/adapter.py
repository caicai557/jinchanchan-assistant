"""
Mac PlayCover 适配器

实现 Mac PlayCover 平台的游戏控制接口
"""

import platform
import time

from PIL import Image

from core.protocols import BasePlatformAdapter, WindowInfo

# 平台检查
IS_MACOS = platform.system() == "Darwin"

if IS_MACOS:
    try:
        import Quartz
        from Quartz import (
            CGEventCreateKeyboardEvent,
            CGEventCreateMouseEvent,
            CGEventPost,
            CGRectNull,
            CGWindowListCreateImage,
            kCGEventKeyDown,
            kCGEventKeyUp,
            kCGEventLeftMouseDown,
            kCGEventLeftMouseUp,
            kCGEventMouseMoved,
            kCGEventOtherMouseDown,
            kCGEventOtherMouseUp,
            kCGEventRightMouseDown,
            kCGEventRightMouseUp,
            kCGEventScrollWheel,
            kCGHIDEventTap,
            kCGMouseButtonCenter,
            kCGMouseButtonLeft,
            kCGMouseButtonRight,
            kCGWindowImageDefault,
            kCGWindowListOptionIncludingWindow,
            kCGWindowListOptionOnScreenOnly,
        )

        QUARTZ_AVAILABLE = True
    except ImportError:
        QUARTZ_AVAILABLE = False

    try:
        import mss

        MSS_AVAILABLE = True
    except ImportError:
        MSS_AVAILABLE = False
else:
    QUARTZ_AVAILABLE = False
    MSS_AVAILABLE = False


class MacPlayCoverAdapter(BasePlatformAdapter):
    """
    Mac PlayCover 平台适配器

    使用 Quartz 和 mss 实现截图和控制
    """

    def __init__(
        self,
        window_title: str = "金铲铲之战",
        use_mss: bool = True,
        fallback_method: str = "quartz",
    ):
        """
        初始化适配器

        Args:
            window_title: 游戏窗口标题
            use_mss: 是否使用 mss 进行截图（性能更好）
            fallback_method: 备用截图方法
        """
        super().__init__(window_title)

        if not IS_MACOS:
            raise RuntimeError("MacPlayCoverAdapter 仅支持 macOS")

        if not QUARTZ_AVAILABLE:
            raise RuntimeError("需要安装 PyObjC: pip install pyobjc-framework-Quartz")

        self.use_mss = use_mss and MSS_AVAILABLE
        self.fallback_method = fallback_method

        # 初始化窗口管理器
        from platforms.mac_playcover.window_manager import WindowManager

        self.window_manager = WindowManager()

        # 查找游戏窗口
        self._find_window()

    def _find_window(self) -> WindowInfo | None:
        """查找游戏窗口"""
        # 尝试精确匹配
        win = self.window_manager.find_window_by_title(self.window_title, exact_match=False)

        if win is None:
            # 尝试其他可能的名称
            win = self.window_manager.find_game_window()

        if win:
            self._window_info = win
            self._scale_factor = self.window_manager.get_scale_factor(win.window_id)
        else:
            self._window_info = None
            self._scale_factor = 1.0

        return self._window_info

    def get_screenshot(self) -> Image.Image:
        """获取游戏窗口截图（按窗口 ID 捕获，不受遮挡影响）"""
        info = self.get_window_info()
        if info is None or info.window_id is None:
            raise RuntimeError(f"未找到游戏窗口: {self.window_title}")

        image_ref = CGWindowListCreateImage(
            CGRectNull,
            kCGWindowListOptionIncludingWindow,
            info.window_id,
            kCGWindowImageDefault,
        )
        if image_ref is None:
            raise RuntimeError("窗口截图失败")
        return self._cgimage_to_pil(image_ref)

    def _capture_impl(self, rect: tuple[int, int, int, int]) -> Image.Image:
        """
        截图实现

        Args:
            rect: (left, top, width, height)
        """
        if self.use_mss:
            return self._capture_with_mss(rect)
        else:
            return self._capture_with_quartz(rect)

    def _capture_with_mss(self, rect: tuple[int, int, int, int]) -> Image.Image:
        """使用 mss 截图（更快）"""
        import mss

        left, top, width, height = rect
        monitor = {
            "left": left,
            "top": top,
            "width": width,
            "height": height,
        }

        with mss.mss() as sct:
            screenshot = sct.grab(monitor)
            return Image.frombytes("RGB", screenshot.size, screenshot.rgb)

    def _capture_with_quartz(self, rect: tuple[int, int, int, int]) -> Image.Image:
        """使用 Quartz 截图"""
        left, top, width, height = rect

        # 创建截图区域
        region = Quartz.CGRectMake(left, top, width, height)

        # 截取屏幕
        image_ref = CGWindowListCreateImage(
            region,
            kCGWindowListOptionOnScreenOnly,
            Quartz.kCGNullWindowID,
            kCGWindowImageDefault,
        )

        if image_ref is None:
            raise RuntimeError("截图失败")

        # 转换为 PIL Image
        return self._cgimage_to_pil(image_ref)

    def _cgimage_to_pil(self, image_ref) -> Image.Image:
        """将 CGImage 转换为 PIL Image"""
        width = Quartz.CGImageGetWidth(image_ref)
        height = Quartz.CGImageGetHeight(image_ref)
        bpr = Quartz.CGImageGetBytesPerRow(image_ref)

        provider = Quartz.CGImageGetDataProvider(image_ref)
        raw = Quartz.CGDataProviderCopyData(provider)
        buf = bytes(raw)

        # stride 参数处理行填充 (bpr 可能 > width*4)
        image = Image.frombytes("RGBA", (width, height), buf, "raw", "BGRA", bpr, 1)
        return image.convert("RGB")

    def _click_impl(self, x: int, y: int, button: str = "left") -> bool:
        """
        点击实现

        Args:
            x: X 坐标
            y: Y 坐标
            button: 鼠标按钮
        """
        # 确保游戏窗口在前台
        self.activate_game()
        time.sleep(0.05)
        # 映射按钮
        button_map = {
            "left": (kCGMouseButtonLeft, kCGEventLeftMouseDown, kCGEventLeftMouseUp),
            "right": (kCGMouseButtonRight, kCGEventRightMouseDown, kCGEventRightMouseUp),
            "middle": (kCGMouseButtonCenter, kCGEventOtherMouseDown, kCGEventOtherMouseUp),
        }

        if button not in button_map:
            button = "left"

        mouse_button, down_event_type, up_event_type = button_map[button]

        # 移动鼠标
        move_event = CGEventCreateMouseEvent(None, kCGEventMouseMoved, (x, y), mouse_button)
        CGEventPost(kCGHIDEventTap, move_event)

        # 按下
        down_event = CGEventCreateMouseEvent(None, down_event_type, (x, y), mouse_button)
        CGEventPost(kCGHIDEventTap, down_event)

        # 短暂延迟
        time.sleep(0.05)

        # 释放
        up_event = CGEventCreateMouseEvent(None, up_event_type, (x, y), mouse_button)
        CGEventPost(kCGHIDEventTap, up_event)

        return True

    def drag(
        self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5
    ) -> bool:
        """
        拖动操作

        Args:
            start_x: 起点X
            start_y: 起点Y
            end_x: 终点X
            end_y: 终点Y
            duration: 持续时间
        """
        # 移动到起点
        move_event = CGEventCreateMouseEvent(
            None, kCGEventMouseMoved, (start_x, start_y), kCGMouseButtonLeft
        )
        CGEventPost(kCGHIDEventTap, move_event)

        # 按下
        down_event = CGEventCreateMouseEvent(
            None, kCGEventLeftMouseDown, (start_x, start_y), kCGMouseButtonLeft
        )
        CGEventPost(kCGHIDEventTap, down_event)

        # 拖动到终点
        steps = int(duration * 60)  # 60 FPS
        for i in range(steps + 1):
            t = i / steps
            x = start_x + (end_x - start_x) * t
            y = start_y + (end_y - start_y) * t

            drag_event = CGEventCreateMouseEvent(
                None, kCGEventMouseMoved, (x, y), kCGMouseButtonLeft
            )
            CGEventPost(kCGHIDEventTap, drag_event)
            time.sleep(duration / steps)

        # 释放
        up_event = CGEventCreateMouseEvent(
            None, kCGEventLeftMouseUp, (end_x, end_y), kCGMouseButtonLeft
        )
        CGEventPost(kCGHIDEventTap, up_event)

        return True

    def scroll(self, x: int, y: int, clicks: int = 1) -> bool:
        """
        滚动操作

        Args:
            x: X 坐标
            y: Y 坐标
            clicks: 滚动次数（正数向上，负数向下）
        """
        # 移动到目标位置
        move_event = CGEventCreateMouseEvent(None, kCGEventMouseMoved, (x, y), kCGMouseButtonLeft)
        CGEventPost(kCGHIDEventTap, move_event)

        # 创建滚动事件
        scroll_event = CGEventCreateMouseEvent(
            None, kCGEventScrollWheel, (x, y), kCGMouseButtonLeft
        )

        # 设置滚动量
        Quartz.CGEventSetIntegerValueField(
            scroll_event, Quartz.kCGScrollWheelEventDeltaAxis1, clicks
        )

        CGEventPost(kCGHIDEventTap, scroll_event)
        return True

    def type_text(self, text: str, interval: float = 0.05) -> bool:
        """输入文本"""
        for char in text:
            # 获取字符的 keycode
            keycode = self._char_to_keycode(char)
            if keycode:
                self.press_key(str(keycode))
                time.sleep(interval)
        return True

    def press_key(self, key: str) -> bool:
        """
        按下按键

        Args:
            key: 按键名称或 keycode
        """
        keycode = self._get_keycode(key)
        if keycode is None:
            return False

        # 按下
        down_event = CGEventCreateKeyboardEvent(None, keycode, True)
        CGEventPost(kCGHIDEventTap, down_event)

        time.sleep(0.05)

        # 释放
        up_event = CGEventCreateKeyboardEvent(None, keycode, False)
        CGEventPost(kCGHIDEventTap, up_event)

        return True

    def is_game_active(self) -> bool:
        """检查游戏窗口是否激活"""
        if self._window_info is None or self._window_info.window_id is None:
            return False
        return self.window_manager.is_window_active(self._window_info.window_id)

    def activate_game(self) -> bool:
        """激活游戏窗口"""
        if self._window_info is None:
            self._find_window()
            if self._window_info is None:
                return False
        if self._window_info.window_id is None:
            return False
        return self.window_manager.activate_window(self._window_info.window_id)

    def get_scale_factor(self) -> float:
        """获取缩放因子"""
        return self._scale_factor or 1.0

    def _get_keycode(self, key: str) -> int | None:
        """获取按键的 keycode"""
        # 常用按键映射
        key_map = {
            "enter": 36,
            "return": 36,
            "escape": 53,
            "esc": 53,
            "tab": 48,
            "space": 49,
            "delete": 51,
            "backspace": 51,
            "arrow_up": 126,
            "arrow_down": 125,
            "arrow_left": 123,
            "arrow_right": 124,
            "f1": 122,
            "f2": 120,
            "f3": 99,
            "f4": 118,
            "f5": 96,
            "f6": 97,
            "f7": 98,
            "f8": 100,
            "f9": 101,
            "f10": 109,
            "f11": 103,
            "f12": 111,
        }

        # 检查是否是特殊键
        key_lower = key.lower()
        if key_lower in key_map:
            return key_map[key_lower]

        # 检查是否是数字 keycode
        if key.isdigit():
            return int(key)

        # 字母键
        if len(key) == 1 and key.isalpha():
            # A-Z 对应 keycode 0-25
            return ord(key.upper()) - ord("A")

        return None

    def _char_to_keycode(self, char: str) -> int | None:
        """字符转 keycode"""
        if len(char) != 1:
            return None

        if char.isalpha():
            return ord(char.upper()) - ord("A")
        elif char.isdigit():
            # 数字键
            return ord(char) - ord("0") + 82
        elif char == " ":
            return 49
        elif char == "\n":
            return 36

        return None

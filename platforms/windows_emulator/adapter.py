"""
Windows 模拟器适配器

实现 Windows 模拟器平台的游戏控制接口
"""

import platform

from PIL import Image

from core.protocols import BasePlatformAdapter, WindowInfo

IS_WINDOWS = platform.system() == "Windows"


class WindowsEmulatorAdapter(BasePlatformAdapter):
    """
    Windows 模拟器适配器

    通过 ADB 与模拟器通信
    """

    def __init__(
        self,
        adb_path: str = "adb",
        device_id: str | None = None,
        host: str = "127.0.0.1",
        port: int = 5555,
        emulator_type: str = "auto",
    ):
        """
        初始化适配器

        Args:
            adb_path: ADB 可执行文件路径
            device_id: 设备 ID
            host: 模拟器主机
            port: 模拟器端口
            emulator_type: 模拟器类型 ("auto" 自动检测)
        """
        super().__init__("金铲铲之战")

        from platforms.windows_emulator.adb_controller import ADBController

        self.adb = ADBController(adb_path=adb_path, device_id=device_id, host=host, port=port)

        self.emulator_type = emulator_type
        self._screen_size: tuple[int, int] | None = None

        # 连接模拟器
        if not self.adb.connect():
            raise RuntimeError("无法连接到模拟器")

    def _find_window(self) -> WindowInfo | None:
        """
        查找窗口（对于模拟器，返回虚拟窗口信息）
        """
        try:
            width, height = self.adb.get_screen_size()
            self._screen_size = (width, height)

            return WindowInfo(
                title="金铲铲之战", left=0, top=0, width=width, height=height, window_id=None
            )
        except Exception:
            return None

    def _capture_impl(self, rect: tuple[int, int, int, int]) -> Image.Image:
        """
        截图实现

        注：ADB 截图会获取整个屏幕，rect 参数用于裁剪
        """
        # 获取完整截图
        image = self.adb.screenshot()

        # 如果指定了区域，进行裁剪
        left, top, width, height = rect
        if left != 0 or top != 0:
            # 对于模拟器，通常左上角就是 (0, 0)
            pass

        return image

    def _click_impl(self, x: int, y: int, button: str = "left") -> bool:
        """
        点击实现

        Args:
            x: X 坐标（模拟器内坐标）
            y: Y 坐标（模拟器内坐标）
            button: 鼠标按钮（ADB 只支持左键）
        """
        if button != "left":
            # ADB 不支持右键
            return False

        return self.adb.tap(x, y)

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
            duration: 持续时间（秒）
        """
        # ADB 使用毫秒
        duration_ms = int(duration * 1000)
        return self.adb.swipe(start_x, start_y, end_x, end_y, duration_ms)

    def scroll(self, x: int, y: int, clicks: int = 1) -> bool:
        """
        滚动操作

        通过模拟滑动手势实现
        """
        # 向上滚动
        if clicks > 0:
            return self.adb.swipe(x, y + 100, x, y - 100, 300)
        # 向下滚动
        else:
            return self.adb.swipe(x, y - 100, x, y + 100, 300)

    def type_text(self, text: str, interval: float = 0.05) -> bool:
        """输入文本"""
        # ADB input text 只支持 ASCII
        ascii_text = "".join(c for c in text if ord(c) < 128)
        if ascii_text:
            return self.adb.input_text(ascii_text)
        return True

    def press_key(self, key: str) -> bool:
        """
        按下按键

        Args:
            key: 按键名称
        """
        keycode_map = {
            "enter": 66,
            "return": 66,
            "escape": 111,
            "esc": 111,
            "back": 4,
            "home": 3,
            "menu": 82,
            "tab": 61,
            "space": 62,
            "delete": 67,
            "backspace": 67,
            "arrow_up": 19,
            "arrow_down": 20,
            "arrow_left": 21,
            "arrow_right": 22,
        }

        key_lower = key.lower()
        if key_lower in keycode_map:
            return self.adb.press_key(keycode_map[key_lower])

        return False

    def is_game_active(self) -> bool:
        """检查模拟器是否连接"""
        return self.adb.is_connected()

    def activate_game(self) -> bool:
        """激活游戏（对于模拟器，尝试拉起游戏应用）"""
        # 尝试启动游戏
        package_name = "com.tencent.tmgp.sgame"  # 金铲铲之战的包名
        try:
            self.adb.run_shell_command(
                f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
            )
            return True
        except Exception:
            return False

    def get_scale_factor(self) -> float:
        """获取缩放因子（模拟器通常为 1.0）"""
        return 1.0

    def get_screenshot(self) -> Image.Image:
        """获取截图（重写以直接使用 ADB）"""
        return self.adb.screenshot()

    def get_game_window_rect(self) -> tuple[int, int, int, int]:
        """获取游戏窗口矩形"""
        if self._screen_size is None:
            self._find_window()

        if self._screen_size:
            return (0, 0, self._screen_size[0], self._screen_size[1])

        raise RuntimeError("无法获取屏幕尺寸")

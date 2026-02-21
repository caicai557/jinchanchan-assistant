"""
ADB 控制器

通过 ADB 与 Android 模拟器通信
"""

import io
import subprocess

from PIL import Image


class ADBController:
    """
    ADB 控制器

    封装常用的 ADB 命令，用于与模拟器交互
    """

    def __init__(
        self,
        adb_path: str = "adb",
        device_id: str | None = None,
        host: str = "127.0.0.1",
        port: int = 5555,
    ):
        """
        初始化 ADB 控制器

        Args:
            adb_path: adb 可执行文件路径
            device_id: 设备 ID（可选，如果不指定会自动连接）
            host: 模拟器主机
            port: 模拟器端口
        """
        self.adb_path = adb_path
        self.device_id = device_id
        self.host = host
        self.port = port
        self._screen_size: tuple[int, int] | None = None

    def connect(self) -> bool:
        """连接到模拟器"""
        # 先尝试断开
        self._run_command(["disconnect", f"{self.host}:{self.port}"])

        # 连接
        result = self._run_command(["connect", f"{self.host}:{self.port}"])
        if "connected" in result.lower():
            # 如果没有指定设备ID，尝试获取
            if self.device_id is None:
                devices = self.get_devices()
                if devices:
                    self.device_id = f"{self.host}:{self.port}"
            return True
        return False

    def disconnect(self) -> bool:
        """断开连接"""
        result = self._run_command(["disconnect", f"{self.host}:{self.port}"])
        return "disconnected" in result.lower() or "not connected" in result.lower()

    def is_connected(self) -> bool:
        """检查是否已连接"""
        devices = self.get_devices()
        target = self.device_id or f"{self.host}:{self.port}"
        return any(target in d for d in devices)

    def get_devices(self) -> list[str]:
        """获取已连接设备列表"""
        result = self._run_command(["devices"])
        lines = result.strip().split("\n")
        devices = []
        for line in lines[1:]:  # 跳过标题行
            if "\t" in line:
                device_id, status = line.split("\t")
                if status == "device":
                    devices.append(device_id)
        return devices

    def screenshot(self) -> Image.Image:
        """截取屏幕"""
        # 使用 screencap 获取截图
        result = self._run_command_raw(["exec-out", "screencap", "-p"], capture_output=True)

        if result.returncode != 0:
            raise RuntimeError(f"截图失败: {result.stderr}")

        # 转换为 PIL Image
        image = Image.open(io.BytesIO(result.stdout))
        return image.convert("RGB")

    def screenshot_to_file(self, local_path: str) -> bool:
        """截图并保存到文件"""
        try:
            image = self.screenshot()
            image.save(local_path)
            return True
        except Exception:
            return False

    def tap(self, x: int, y: int) -> bool:
        """点击屏幕"""
        result = self._run_command(["shell", "input", "tap", str(x), str(y)])
        return "error" not in result.lower()

    def swipe(
        self, start_x: int, start_y: int, end_x: int, end_y: int, duration: int = 300
    ) -> bool:
        """滑动屏幕"""
        result = self._run_command(
            [
                "shell",
                "input",
                "swipe",
                str(start_x),
                str(start_y),
                str(end_x),
                str(end_y),
                str(duration),
            ]
        )
        return "error" not in result.lower()

    def long_press(self, x: int, y: int, duration: int = 1000) -> bool:
        """长按"""
        return self.swipe(x, y, x, y, duration)

    def input_text(self, text: str) -> bool:
        """输入文本（仅支持 ASCII）"""
        # 对文本进行转义
        text = text.replace(" ", "%s")
        text = text.replace("&", "\\&")

        result = self._run_command(["shell", "input", "text", text])
        return "error" not in result.lower()

    def press_key(self, keycode: int) -> bool:
        """
        按下按键

        常用 keycode:
        - 3: HOME
        - 4: BACK
        - 24: VOLUME_UP
        - 25: VOLUME_DOWN
        - 26: POWER
        - 66: ENTER
        - 67: DEL
        """
        result = self._run_command(["shell", "input", "keyevent", str(keycode)])
        return "error" not in result.lower()

    def get_screen_size(self) -> tuple[int, int]:
        """获取屏幕尺寸"""
        if self._screen_size:
            return self._screen_size

        result = self._run_command(["shell", "wm", "size"])
        # 格式: Physical size: 1920x1080
        if "Physical size:" in result or "Override size:" in result:
            for line in result.split("\n"):
                if "size:" in line:
                    size_str = line.split(":")[-1].strip()
                    width, height = size_str.split("x")
                    self._screen_size = (int(width), int(height))
                    return self._screen_size

        raise RuntimeError("无法获取屏幕尺寸")

    def get_density(self) -> int:
        """获取屏幕密度"""
        result = self._run_command(["shell", "wm", "density"])
        if "density:" in result:
            for line in result.split("\n"):
                if "density:" in line:
                    return int(line.split(":")[-1].strip())
        return 320  # 默认密度

    def push_file(self, local_path: str, remote_path: str) -> bool:
        """推送文件到设备"""
        result = self._run_command(["push", local_path, remote_path])
        return "error" not in result.lower()

    def pull_file(self, remote_path: str, local_path: str) -> bool:
        """从设备拉取文件"""
        result = self._run_command(["pull", remote_path, local_path])
        return "error" not in result.lower()

    def run_shell_command(self, command: str) -> str:
        """运行 shell 命令"""
        return self._run_command(["shell", command])

    def _run_command(self, args: list[str]) -> str:
        """运行 ADB 命令并返回输出"""
        result = self._run_command_raw(args, capture_output=True)
        return (result.stdout or b"").decode("utf-8", errors="ignore")

    def _run_command_raw(
        self, args: list[str], capture_output: bool = True
    ) -> subprocess.CompletedProcess:
        """运行 ADB 命令"""
        cmd = [self.adb_path]

        # 如果指定了设备，添加 -s 参数
        if self.device_id:
            cmd.extend(["-s", self.device_id])

        cmd.extend(args)

        return subprocess.run(cmd, capture_output=capture_output, timeout=30)


# 常用模拟器端口映射
EMULATOR_PORTS = {
    "雷电模拟器": [5555, 5557, 5559],  # 多开时端口递增
    "夜神模拟器": [62001, 62025, 62026],
    "MuMu模拟器": [7555],
    "BlueStacks": [5555],
    "逍遥模拟器": [21503],
    "Genymotion": [5555],
}


def find_emulator(adb_path: str = "adb") -> ADBController | None:
    """
    自动查找并连接模拟器

    Args:
        adb_path: adb 路径

    Returns:
        ADBController 或 None
    """
    # 首先检查已连接的设备
    controller = ADBController(adb_path=adb_path)
    devices = controller.get_devices()

    if devices:
        controller.device_id = devices[0]
        return controller

    # 尝试连接常用端口
    for emulator, ports in EMULATOR_PORTS.items():
        for port in ports:
            controller = ADBController(adb_path=adb_path, port=port)
            if controller.connect():
                return controller

    return None

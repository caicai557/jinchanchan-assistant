"""
Windows 模拟器平台
"""

from platforms.windows_emulator.adapter import WindowsEmulatorAdapter
from platforms.windows_emulator.adb_controller import ADBController

__all__ = [
    "WindowsEmulatorAdapter",
    "ADBController",
]

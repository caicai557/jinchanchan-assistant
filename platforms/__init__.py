"""
平台适配模块
"""

from platforms.mac_playcover.adapter import MacPlayCoverAdapter
from platforms.windows_emulator.adapter import WindowsEmulatorAdapter

__all__ = [
    "MacPlayCoverAdapter",
    "WindowsEmulatorAdapter",
]

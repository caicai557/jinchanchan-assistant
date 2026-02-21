"""
Mac PlayCover 平台适配器
"""

from platforms.mac_playcover.adapter import MacPlayCoverAdapter
from platforms.mac_playcover.window_manager import WindowManager

__all__ = [
    "MacPlayCoverAdapter",
    "WindowManager",
]

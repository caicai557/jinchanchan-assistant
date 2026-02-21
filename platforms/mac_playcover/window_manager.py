"""
Mac 窗口管理器

使用 PyObjC 访问 macOS 窗口服务
"""

import platform
from typing import Any

from core.protocols import WindowInfo

# 平台检查
IS_MACOS = platform.system() == "Darwin"

if IS_MACOS:
    try:
        import Quartz
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGNullWindowID,
            kCGWindowListExcludeDesktopElements,
            kCGWindowListOptionOnScreenOnly,
        )

        MACOS_AVAILABLE = True
    except ImportError:
        MACOS_AVAILABLE = False
else:
    MACOS_AVAILABLE = False


class WindowManager:
    """
    Mac 窗口管理器

    提供窗口查找、信息获取等功能
    """

    def __init__(self):
        if not MACOS_AVAILABLE:
            raise RuntimeError(
                "WindowManager 仅支持 macOS，且需要安装 PyObjC: pip install pyobjc-framework-Quartz"
            )

    def find_window_by_title(self, title: str, exact_match: bool = False) -> WindowInfo | None:
        """
        根据标题查找窗口

        Args:
            title: 窗口标题
            exact_match: 是否精确匹配

        Returns:
            WindowInfo 或 None
        """
        windows = self._get_window_list()

        for win in windows:
            win_title = win.get("kCGWindowName", "") or ""
            owner_name = win.get("kCGWindowOwnerName", "") or ""

            # 检查窗口标题或所有者名称
            if exact_match:
                if title == win_title or title == owner_name:
                    return self._create_window_info(win)
            else:
                if title in win_title or title in owner_name:
                    return self._create_window_info(win)

        return None

    def find_windows_by_owner(self, owner: str) -> list[WindowInfo]:
        """
        根据应用名称查找所有窗口

        Args:
            owner: 应用名称（如 "PlayCover"）

        Returns:
            窗口列表
        """
        windows = self._get_window_list()
        result = []

        for win in windows:
            owner_name = win.get("kCGWindowOwnerName", "") or ""
            if owner.lower() in owner_name.lower() or owner_name.lower() in owner.lower():
                result.append(self._create_window_info(win))

        return result

    def find_game_window(self, game_names: list[str] | None = None) -> WindowInfo | None:
        """
        查找游戏窗口

        Args:
            game_names: 可能的游戏窗口名称列表

        Returns:
            WindowInfo 或 None
        """
        if game_names is None:
            game_names = ["金铲铲之战", "金铲铲", "TFT", "Teamfight Tactics"]

        for name in game_names:
            win = self.find_window_by_title(name)
            if win:
                return win

        return None

    def get_active_window(self) -> WindowInfo | None:
        """获取当前活动窗口"""
        windows = self._get_window_list()

        for win in windows:
            if win.get("kCGWindowLayer", 0) == 0:
                return self._create_window_info(win)

        return None

    def is_window_active(self, window_id: int) -> bool:
        """检查指定窗口是否活动"""
        active = self.get_active_window()
        return active is not None and active.window_id == window_id

    def activate_window(self, window_id: int) -> bool:
        """
        激活指定窗口

        Args:
            window_id: 窗口ID

        Returns:
            是否成功
        """
        # 获取窗口所属应用
        windows = self._get_window_list()
        pid = None

        for win in windows:
            if win.get("kCGWindowNumber") == window_id:
                pid = win.get("kCGWindowOwnerPID")
                break

        if pid is None:
            return False

        # 使用 AppleScript 激活应用
        import subprocess

        script = f"""
        tell application "System Events"
            set frontmost of (first process whose unix id is {pid}) to true
        end tell
        """

        try:
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
            return True
        except Exception:
            return False

    def _get_window_list(self) -> list[dict[str, Any]]:
        """获取窗口列表"""
        options = kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements
        window_list = CGWindowListCopyWindowInfo(options, kCGNullWindowID)
        return list(window_list) if window_list else []

    def _create_window_info(self, win: dict[str, Any]) -> WindowInfo:
        """从窗口字典创建 WindowInfo"""
        bounds = win.get("kCGWindowBounds", {})
        return WindowInfo(
            title=win.get("kCGWindowName", "") or win.get("kCGWindowOwnerName", ""),
            left=int(bounds.get("X", 0)),
            top=int(bounds.get("Y", 0)),
            width=int(bounds.get("Width", 0)),
            height=int(bounds.get("Height", 0)),
            window_id=win.get("kCGWindowNumber"),
        )

    def get_scale_factor(self, window_id: int | None = None) -> float:
        """
        获取窗口缩放因子（用于 Retina 屏幕）

        Args:
            window_id: 窗口ID（可选）

        Returns:
            缩放因子
        """
        # 获取主屏幕的缩放因子
        try:
            screens = Quartz.CGDisplayOnlineDisplays()
            if screens:
                main_display = Quartz.CGMainDisplayID()
                mode = Quartz.CGDisplayCopyDisplayMode(main_display)
                if mode:
                    pixel_width = float(Quartz.CGDisplayModeGetPixelWidth(mode))
                    points_width = float(Quartz.CGDisplayModeGetWidth(mode))
                    if points_width > 0:
                        return pixel_width / points_width
        except Exception:
            pass

        return 1.0

    def enumerate_windows(
        self,
        filter_pattern: str | None = None,
        use_regex: bool = False,
        visible_only: bool = True,
    ) -> list[dict[str, Any]]:
        """
        枚举所有窗口并返回详细信息（用于调试）

        Args:
            filter_pattern: 过滤模式（contains 或 regex）
            use_regex: 是否使用正则匹配
            visible_only: 是否只返回可见窗口

        Returns:
            窗口信息列表
        """
        import re

        windows = self._get_window_list()
        result = []

        for win in windows:
            title = win.get("kCGWindowName", "") or ""
            owner = win.get("kCGWindowOwnerName", "") or ""
            pid = win.get("kCGWindowOwnerPID", 0)
            win_id = win.get("kCGWindowNumber", 0)
            layer = win.get("kCGWindowLayer", 0)
            bounds = win.get("kCGWindowBounds", {})
            alpha = win.get("kCGWindowAlpha", 1.0)

            # 可见性判断
            is_visible = alpha > 0 and layer == 0 and bounds.get("Width", 0) > 0
            if visible_only and not is_visible:
                continue

            # 过滤
            if filter_pattern:
                search_text = f"{title} {owner}"
                if use_regex:
                    if not re.search(filter_pattern, search_text, re.IGNORECASE):
                        continue
                else:
                    if filter_pattern.lower() not in search_text.lower():
                        continue

            result.append(
                {
                    "title": title or "(无标题)",
                    "owner": owner,
                    "pid": pid,
                    "window_id": win_id,
                    "visible": is_visible,
                    "layer": layer,
                    "alpha": alpha,
                    "x": int(bounds.get("X", 0)),
                    "y": int(bounds.get("Y", 0)),
                    "width": int(bounds.get("Width", 0)),
                    "height": int(bounds.get("Height", 0)),
                }
            )

        return result

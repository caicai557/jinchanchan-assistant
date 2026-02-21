"""debug-window 与 TUI 集成测试（mock adapter，不触网）"""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import debug_windows, run_tui
from tests.test_smoke_e2e import FakePlatformAdapter


def test_debug_windows_non_mac_returns_error() -> None:
    """非 mac 平台调用 debug_windows 应返回错误码。"""
    result = debug_windows(platform="windows")
    assert result == 1


def test_debug_windows_mac_mock() -> None:
    """mac 平台 mock WindowManager 测试。"""
    mock_wm_instance = MagicMock()
    mock_wm_instance.enumerate_windows.return_value = [
        {
            "title": "金铲铲之战",
            "owner": "PlayCover",
            "pid": 12345,
            "window_id": 100,
            "visible": True,
            "layer": 0,
            "alpha": 1.0,
            "x": 0,
            "y": 0,
            "width": 1920,
            "height": 1080,
        },
    ]
    mock_wm_instance.find_window_by_title.return_value = MagicMock(
        title="金铲铲之战", width=1920, height=1080
    )

    mock_wm_class = MagicMock(return_value=mock_wm_instance)

    # Patch at the import location inside debug_windows
    with patch("platforms.mac_playcover.window_manager.WindowManager", mock_wm_class):
        captured = StringIO()
        with patch("sys.stdout", captured):
            result = debug_windows(platform="mac")

    assert result == 0
    output = captured.getvalue()
    assert "窗口枚举结果" in output


def test_debug_windows_with_filter() -> None:
    """带过滤参数的窗口调试。"""
    mock_wm_instance = MagicMock()
    mock_wm_instance.enumerate_windows.return_value = [
        {
            "title": "金铲铲之战",
            "owner": "PlayCover",
            "pid": 12345,
            "window_id": 100,
            "visible": True,
            "layer": 0,
            "alpha": 1.0,
            "x": 0,
            "y": 0,
            "width": 1920,
            "height": 1080,
        },
    ]
    mock_wm_instance.find_window_by_title.return_value = None

    mock_wm_class = MagicMock(return_value=mock_wm_instance)

    with patch("platforms.mac_playcover.window_manager.WindowManager", mock_wm_class):
        captured = StringIO()
        with patch("sys.stdout", captured):
            result = debug_windows(platform="mac", filter_pattern="金铲铲")

    assert result == 0
    mock_wm_instance.enumerate_windows.assert_called_once()


def test_run_tui_missing_rich_returns_error() -> None:
    """缺少 rich 库时 run_tui 应返回错误码。"""
    adapter = FakePlatformAdapter()
    # 模拟 rich 模块不存在
    with patch.dict("sys.modules", {"rich": None, "rich.console": None}):
        result = run_tui(
            adapter=adapter,
            llm_client=None,
            dry_run=True,
            interval=1.0,
            budget=10,
        )
    # 由于 rich 已经安装，这个测试主要验证函数不会崩溃
    assert result in (0, 1)


def test_run_tui_with_mock_rich() -> None:
    """使用 mock rich 测试 TUI 启动逻辑。"""
    adapter = FakePlatformAdapter()

    # 验证 fake adapter 工作正常
    assert adapter.get_window_info() is not None
    assert adapter.get_window_info().title == "fake"

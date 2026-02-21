"""坐标缩放器测试"""

from __future__ import annotations

from core.coordinate_scaler import CoordinateScaler, Resolution


def test_reference_resolution() -> None:
    """参考分辨率测试"""
    ref = Resolution.HD_1080()
    assert ref.width == 1920
    assert ref.height == 1080
    assert ref.aspect_ratio() == 16 / 9


def test_no_scaling_at_reference() -> None:
    """参考分辨率下不缩放"""
    scaler = CoordinateScaler()
    assert scaler.is_reference() is True
    assert scaler.scale_point(100, 200) == (100, 200)
    assert scaler.scale_size(80, 80) == (80, 80)


def test_scale_2x() -> None:
    """2x 缩放测试"""
    scaler = CoordinateScaler(Resolution(3840, 2160))  # 4K
    assert scaler.scale_point(100, 200) == (200, 400)
    assert scaler.scale_size(80, 80) == (160, 160)


def test_scale_points_batch() -> None:
    """批量缩放测试"""
    scaler = CoordinateScaler(Resolution(1280, 720))  # 2/3 缩放
    points = [(180, 950), (340, 950), (500, 950)]
    scaled = scaler.scale_points(points)
    assert len(scaled) == 3
    assert scaled[0][0] == int(180 * 1280 / 1920)
    assert scaled[0][1] == int(950 * 720 / 1080)


def test_scale_rect() -> None:
    """矩形缩放测试"""
    scaler = CoordinateScaler(Resolution(2560, 1440))
    x, y, w, h = scaler.scale_rect(100, 200, 80, 80)
    assert x == int(100 * 2560 / 1920)
    assert y == int(200 * 1440 / 1080)
    assert w == int(80 * 2560 / 1920)
    assert h == int(80 * 1440 / 1080)


def test_from_window_size() -> None:
    """从窗口尺寸创建"""
    scaler = CoordinateScaler.from_window_size(3096, 2064)
    assert scaler.target.width == 3096
    assert scaler.target.height == 2064
    assert scaler.is_reference() is False


def test_scale_factor() -> None:
    """缩放因子测试"""
    scaler = CoordinateScaler(Resolution(2560, 1440))
    sx, sy = scaler.scale_factor
    assert sx == 2560 / 1920
    assert sy == 1440 / 1080

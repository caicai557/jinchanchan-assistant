"""统一坐标映射测试。"""

from __future__ import annotations

from core.geometry.transform import CoordinateTransform, infer_letterbox_content_rect


def test_map_point_without_offset() -> None:
    transform = CoordinateTransform(base_size=(1920, 1080), current_size=(960, 540))
    assert transform.map_point(192, 108) == (96, 54)


def test_map_rect_with_explicit_content_rect_offset() -> None:
    transform = CoordinateTransform(
        base_size=(1920, 1080),
        current_size=(2000, 1200),
        content_rect=(40, 60, 1920, 1080),
    )
    assert transform.map_rect(100, 200, 80, 40) == (140, 260, 80, 40)
    assert transform.offset == (40, 60)


def test_infer_letterbox_content_rect() -> None:
    rect = infer_letterbox_content_rect((1920, 1080), (1600, 1200))
    # 4:3 窗口中按 16:9 居中，产生上下黑边
    assert rect == (0, 150, 1600, 900)


def test_diagnostics_contains_scale_and_offset() -> None:
    transform = CoordinateTransform(base_size=(1920, 1080), current_size=(2400, 1350))
    diag = transform.diagnostics()
    assert diag["base_size"] == (1920, 1080)
    assert diag["current_size"] == (2400, 1350)
    assert diag["offset"] == (0, 0)
    assert diag["scale"] == (1.25, 1.25)

"""
模板匹配器

使用 OpenCV 进行图像模板匹配
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PIL import Image

if TYPE_CHECKING:
    pass  # numpy only used at runtime, not for type hints

# 延迟导入 cv2 和 numpy
_cv2: Any = None
_np: Any = None


def _get_cv2() -> Any:
    """获取 cv2 模块（延迟导入）"""
    global _cv2
    if _cv2 is None:
        try:
            import cv2

            _cv2 = cv2
        except ImportError as e:
            raise ImportError("模板匹配需要 OpenCV: pip install opencv-python") from e
    return _cv2


def _get_np() -> Any:
    """获取 numpy 模块（延迟导入）"""
    global _np
    if _np is None:
        try:
            import numpy  # type: ignore[import]

            _np = numpy
        except ImportError as e:
            raise ImportError("模板匹配需要 numpy: pip install numpy") from e
    return _np


@dataclass
class MatchResult:
    """匹配结果"""

    x: int
    y: int
    width: int
    height: int
    confidence: float
    template_name: str

    @property
    def center(self) -> tuple[int, int]:
        """获取中心点"""
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        """获取边界框 (x1, y1, x2, y2)"""
        return (self.x, self.y, self.x + self.width, self.y + self.height)


class TemplateMatcher:
    """
    模板匹配器

    支持多尺度匹配、多模板匹配
    """

    def __init__(
        self,
        templates_dir: str | None = None,
        default_threshold: float = 0.8,
        scales: list[float] | None = None,
    ):
        """
        初始化模板匹配器

        Args:
            templates_dir: 模板图片目录
            default_threshold: 默认匹配阈值
            scales: 缩放比例列表（用于多尺度匹配）
        """
        self.default_threshold = default_threshold
        self.scales = scales or [1.0]

        # 加载模板
        self.templates: dict[str, Any] = {}  # np.ndarray at runtime
        self.template_info: dict[str, dict[str, Any]] = {}

        if templates_dir:
            self.load_templates(templates_dir)

    def load_templates(self, directory: str, recursive: bool = True) -> int:
        """
        加载目录中的所有模板图片

        Args:
            directory: 模板目录
            recursive: 是否递归加载

        Returns:
            加载的模板数量
        """
        count = 0
        dir_path = Path(directory)

        if not dir_path.exists():
            return 0

        patterns = ["*.png", "*.jpg", "*.jpeg", "*.bmp"]
        for pattern in patterns:
            for img_path in dir_path.glob(pattern):
                self.add_template(str(img_path))
                count += 1

            if recursive:
                for img_path in dir_path.rglob(pattern):
                    self.add_template(str(img_path))
                    count += 1

        return count

    def add_template(
        self, path: str, name: str | None = None, metadata: dict[str, Any] | None = None
    ) -> bool:
        """
        添加模板

        Args:
            path: 模板图片路径
            name: 模板名称（默认使用文件名）
            metadata: 元数据

        Returns:
            是否添加成功
        """
        cv2 = _get_cv2()
        try:
            # 读取图片
            template = cv2.imread(path, cv2.IMREAD_COLOR)  # type: ignore[union-attr]
            if template is None:
                return False

            # 生成名称
            if name is None:
                name = Path(path).stem

            self.templates[name] = template
            self.template_info[name] = {
                "path": path,
                "width": template.shape[1],
                "height": template.shape[0],
                "metadata": metadata or {},
            }

            return True
        except Exception:
            return False

    def add_template_from_array(
        self, image: Any, name: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """
        从 numpy 数组添加模板

        Args:
            image: 图片数组 (BGR 格式)
            name: 模板名称
            metadata: 元数据
        """
        self.templates[name] = image.copy()
        self.template_info[name] = {
            "path": None,
            "width": image.shape[1],
            "height": image.shape[0],
            "metadata": metadata or {},
        }

    def match(
        self,
        image: Image.Image,
        template_name: str,
        threshold: float | None = None,
        multi_scale: bool = False,
    ) -> MatchResult | None:
        """
        匹配单个模板

        Args:
            image: 待匹配图像
            template_name: 模板名称
            threshold: 匹配阈值
            multi_scale: 是否启用多尺度匹配

        Returns:
            匹配结果或 None
        """
        if template_name not in self.templates:
            return None

        cv2 = _get_cv2()
        np = _get_np()

        threshold = threshold or self.default_threshold
        template = self.templates[template_name]

        # 转换为 OpenCV 格式
        img_array = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)  # type: ignore[union-attr]

        if multi_scale:
            return self._match_multi_scale(img_array, template, template_name, threshold)
        else:
            return self._match_single(img_array, template, template_name, threshold)

    def match_all(
        self,
        image: Image.Image,
        template_names: list[str] | None = None,
        threshold: float | None = None,
        multi_scale: bool = False,
    ) -> list[MatchResult]:
        """
        匹配多个模板

        Args:
            image: 待匹配图像
            template_names: 模板名称列表（None 表示匹配所有）
            threshold: 匹配阈值
            multi_scale: 是否启用多尺度匹配

        Returns:
            匹配结果列表
        """
        threshold = threshold or self.default_threshold

        if template_names is None:
            template_names = list(self.templates.keys())

        results = []
        for name in template_names:
            result = self.match(image, name, threshold, multi_scale)
            if result:
                results.append(result)

        # 按置信度排序
        results.sort(key=lambda r: r.confidence, reverse=True)
        return results

    def find_all_occurrences(
        self,
        image: Image.Image,
        template_name: str,
        threshold: float | None = None,
        min_distance: int = 10,
    ) -> list[MatchResult]:
        """
        查找模板的所有出现位置

        Args:
            image: 待匹配图像
            template_name: 模板名称
            threshold: 匹配阈值
            min_distance: 最小间距（避免重复匹配）

        Returns:
            匹配结果列表
        """
        if template_name not in self.templates:
            return []

        cv2 = _get_cv2()
        np = _get_np()

        threshold = threshold or self.default_threshold
        template = self.templates[template_name]

        # 转换为 OpenCV 格式
        img_array = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)  # type: ignore[union-attr]

        # 执行模板匹配
        result = cv2.matchTemplate(img_array, template, cv2.TM_CCOEFF_NORMED)  # type: ignore[union-attr]
        locations = np.where(result >= threshold)  # type: ignore[union-attr]

        results: list[MatchResult] = []
        h, w = template.shape[:2]

        for pt in zip(*locations[::-1]):
            confidence = result[pt[1], pt[0]]

            # 检查与已有结果的距离
            is_duplicate = False
            for existing in results:
                ex, ey = existing.x, existing.y
                if abs(pt[0] - ex) < min_distance and abs(pt[1] - ey) < min_distance:
                    is_duplicate = True
                    break

            if not is_duplicate:
                results.append(
                    MatchResult(
                        x=int(pt[0]),
                        y=int(pt[1]),
                        width=w,
                        height=h,
                        confidence=float(confidence),
                        template_name=template_name,
                    )
                )

        # 按置信度排序
        results.sort(key=lambda r: r.confidence, reverse=True)
        return results

    def _match_single(
        self, image: Any, template: Any, template_name: str, threshold: float
    ) -> MatchResult | None:
        """单尺度匹配"""
        cv2 = _get_cv2()

        result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)  # type: ignore[union-attr]
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)  # type: ignore[union-attr]

        if max_val >= threshold:
            h, w = template.shape[:2]
            return MatchResult(
                x=int(max_loc[0]),
                y=int(max_loc[1]),
                width=w,
                height=h,
                confidence=float(max_val),
                template_name=template_name,
            )

        return None

    def _match_multi_scale(
        self, image: Any, template: Any, template_name: str, threshold: float
    ) -> MatchResult | None:
        """多尺度匹配"""
        cv2 = _get_cv2()

        best_result = None
        best_confidence: float = 0.0

        h, w = template.shape[:2]

        for scale in self.scales:
            # 缩放模板
            if scale != 1.0:
                new_w = int(w * scale)
                new_h = int(h * scale)
                scaled_template = cv2.resize(template, (new_w, new_h))  # type: ignore[union-attr]
            else:
                scaled_template = template
                new_w, new_h = w, h

            # 执行匹配
            result = cv2.matchTemplate(image, scaled_template, cv2.TM_CCOEFF_NORMED)  # type: ignore[union-attr]
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)  # type: ignore[union-attr]

            if max_val >= threshold and max_val > best_confidence:
                best_confidence = max_val
                best_result = MatchResult(
                    x=int(max_loc[0]),
                    y=int(max_loc[1]),
                    width=new_w,
                    height=new_h,
                    confidence=float(max_val),
                    template_name=template_name,
                )

        return best_result

    def get_template_info(self, name: str) -> dict[str, Any] | None:
        """获取模板信息"""
        return self.template_info.get(name)

    def list_templates(self) -> list[str]:
        """列出所有模板名称"""
        return list(self.templates.keys())


def load_templates_from_directory(directory: str, threshold: float = 0.8) -> TemplateMatcher:
    """
    从目录加载模板

    Args:
        directory: 模板目录
        threshold: 默认阈值

    Returns:
        TemplateMatcher 实例
    """
    matcher = TemplateMatcher(default_threshold=threshold)
    matcher.load_templates(directory)
    return matcher

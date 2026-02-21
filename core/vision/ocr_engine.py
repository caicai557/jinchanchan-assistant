"""
OCR 引擎

支持多种 OCR 后端，默认使用 RapidOCR（PaddleOCR 的 ONNX 版本）
"""

import platform
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
from PIL import Image


class OCREngineType(str, Enum):
    """OCR 引擎类型"""

    RAPIDOCR = "rapidocr"  # RapidOCR (推荐)
    TESSERACT = "tesseract"  # Tesseract OCR
    VISION = "vision"  # macOS Vision Framework
    AUTO = "auto"  # 自动选择


@dataclass
class OCRResult:
    """OCR 识别结果"""

    text: str
    confidence: float
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)

    @property
    def center(self) -> tuple[int, int]:
        """获取文本框中心点"""
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    @property
    def width(self) -> int:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> int:
        return self.bbox[3] - self.bbox[1]


class OCREngine:
    """
    OCR 引擎

    封装多种 OCR 后端，提供统一的识别接口
    """

    def __init__(
        self,
        engine_type: OCREngineType = OCREngineType.AUTO,
        use_gpu: bool = False,
        lang: str = "ch",
    ):
        """
        初始化 OCR 引擎

        Args:
            engine_type: 引擎类型
            use_gpu: 是否使用 GPU
            lang: 语言（ch/en）
        """
        self.engine_type = engine_type
        self.use_gpu = use_gpu
        self.lang = lang

        self._engine: Any | None = None
        self._initialized = False

        # 自动选择引擎
        if engine_type == OCREngineType.AUTO:
            self.engine_type = self._auto_select_engine()

    def _auto_select_engine(self) -> OCREngineType:
        """自动选择最佳引擎"""
        # 优先使用 RapidOCR
        try:
            from rapidocr_onnxruntime import RapidOCR

            return OCREngineType.RAPIDOCR
        except ImportError:
            pass

        # macOS Vision
        if platform.system() == "Darwin":
            try:
                import Vision

                return OCREngineType.VISION
            except ImportError:
                pass

        # Tesseract
        try:
            import pytesseract

            return OCREngineType.TESSERACT
        except ImportError:
            pass

        raise RuntimeError("没有可用的 OCR 引擎，请安装 rapidocr-onnxruntime")

    def initialize(self) -> bool:
        """初始化引擎"""
        if self._initialized:
            return True

        try:
            if self.engine_type == OCREngineType.RAPIDOCR:
                self._init_rapidocr()
            elif self.engine_type == OCREngineType.TESSERACT:
                self._init_tesseract()
            elif self.engine_type == OCREngineType.VISION:
                self._init_vision()

            self._initialized = True
            return True
        except Exception as e:
            print(f"OCR 引擎初始化失败: {e}")
            return False

    def _init_rapidocr(self):
        """初始化 RapidOCR"""
        from rapidocr_onnxruntime import RapidOCR

        self._engine = RapidOCR()

    def _init_tesseract(self):
        """初始化 Tesseract"""
        import pytesseract

        self._engine = pytesseract

    def _init_vision(self):
        """初始化 macOS Vision"""
        import Vision
        from Cocoa import NSURL
        from Quartz import CIImage

        self._engine = {
            "Vision": Vision,
            "NSURL": NSURL,
            "CIImage": CIImage,
        }

    def recognize(
        self, image: Image.Image, regions: list[tuple[int, int, int, int]] | None = None
    ) -> list[OCRResult]:
        """
        识别图像中的文字

        Args:
            image: PIL Image
            regions: 指定识别区域（可选）

        Returns:
            OCR 结果列表
        """
        if not self._initialized:
            self.initialize()

        if self.engine_type == OCREngineType.RAPIDOCR:
            return self._recognize_rapidocr(image, regions)
        elif self.engine_type == OCREngineType.TESSERACT:
            return self._recognize_tesseract(image, regions)
        elif self.engine_type == OCREngineType.VISION:
            return self._recognize_vision(image, regions)

        return []

    def _recognize_rapidocr(
        self, image: Image.Image, regions: list[tuple[int, int, int, int]] | None = None
    ) -> list[OCRResult]:
        """使用 RapidOCR 识别"""
        results = []

        if regions:
            # 对每个区域单独识别
            for region in regions:
                x1, y1, x2, y2 = region
                cropped = image.crop((x1, y1, x2, y2))
                region_results = self._rapidocr_single(cropped)

                # 将结果坐标转换为原图坐标
                for result in region_results:
                    ox1, oy1, ox2, oy2 = result.bbox
                    result.bbox = (ox1 + x1, oy1 + y1, ox2 + x1, oy2 + y1)
                results.extend(region_results)
        else:
            # 识别整张图片
            results = self._rapidocr_single(image)

        return results

    def _rapidocr_single(self, image: Image.Image) -> list[OCRResult]:
        """使用 RapidOCR 识别单张图片"""
        if self._engine is None:
            return []

        # 转换为 numpy 数组
        img_array = np.array(image)

        # 执行 OCR
        result, elapse = self._engine(img_array)

        if result is None:
            return []

        ocr_results: list[OCRResult] = []
        for box, text, confidence in result:
            # box 是四个角点 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            x_coords = [p[0] for p in box]
            y_coords = [p[1] for p in box]

            bbox = (int(min(x_coords)), int(min(y_coords)), int(max(x_coords)), int(max(y_coords)))

            ocr_results.append(OCRResult(text=text, confidence=float(confidence), bbox=bbox))

        return ocr_results

    def _recognize_tesseract(
        self, image: Image.Image, regions: list[tuple[int, int, int, int]] | None = None
    ) -> list[OCRResult]:
        """使用 Tesseract 识别"""
        if self._engine is None:
            return []

        results: list[OCRResult] = []

        if regions:
            for region in regions:
                x1, y1, x2, y2 = region
                cropped = image.crop((x1, y1, x2, y2))
                text = self._engine.image_to_string(cropped, lang=self.lang)
                if text.strip():
                    results.append(OCRResult(text=text.strip(), confidence=0.8, bbox=region))
        else:
            data = self._engine.image_to_data(
                image, lang=self.lang, output_type=self._engine.Output.DICT
            )

            for i, text in enumerate(data["text"]):
                if text.strip():
                    results.append(
                        OCRResult(
                            text=text.strip(),
                            confidence=data["conf"][i] / 100.0,
                            bbox=(
                                data["left"][i],
                                data["top"][i],
                                data["left"][i] + data["width"][i],
                                data["top"][i] + data["height"][i],
                            ),
                        )
                    )

        return results

    def _recognize_vision(
        self, image: Image.Image, regions: list[tuple[int, int, int, int]] | None = None
    ) -> list[OCRResult]:
        """使用 macOS Vision 识别"""
        # 简化实现，Vision Framework 需要更多 Cocoa 代码
        # 这里提供一个基础实现
        results: list[OCRResult] = []

        if self._engine is None:
            return results

        try:
            _Vision = self._engine["Vision"]
            _NSURL = self._engine["NSURL"]
            _CIImage = self._engine["CIImage"]

            # 将 PIL Image 转换为 CIImage
            # ... 需要更多代码
            # 目前 Vision OCR 尚未完全实现

        except Exception as e:
            print(f"Vision OCR 失败: {e}")

        return results

    def recognize_number(
        self, image: Image.Image, region: tuple[int, int, int, int] | None = None
    ) -> int | None:
        """
        识别数字

        Args:
            image: 图像
            region: 区域

        Returns:
            识别的数字或 None
        """
        if region:
            image = image.crop(region)

        results = self.recognize(image)

        for result in results:
            # 尝试提取数字
            import re

            numbers = re.findall(r"\d+", result.text)
            if numbers:
                return int(numbers[0])

        return None

    def recognize_text_in_region(
        self, image: Image.Image, region: tuple[int, int, int, int]
    ) -> str | None:
        """
        识别指定区域的文字

        Args:
            image: 图像
            region: (x1, y1, x2, y2)

        Returns:
            识别的文本
        """
        results = self.recognize(image, [region])
        if results:
            # 按位置排序并合并
            results.sort(key=lambda r: (r.bbox[1], r.bbox[0]))
            return " ".join(r.text for r in results)
        return None


# 便捷函数
def create_ocr_engine(engine_type: str = "auto", use_gpu: bool = False) -> OCREngine:
    """创建 OCR 引擎"""
    return OCREngine(engine_type=OCREngineType(engine_type), use_gpu=use_gpu)

"""
能力矩阵

定义 Lite vs Full 两种 flavor，每项能力可机器判定
"""

import logging
import os
import platform
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("capabilities")


class Flavor(str, Enum):
    """能力层级"""

    LITE = "lite"  # 基础能力，无重依赖
    FULL = "full"  # 完整能力，包含 OCR/模板匹配/LLM


class CapabilityStatus(str, Enum):
    """能力状态"""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    PARTIAL = "partial"
    NOT_CONFIGURED = "not_configured"


@dataclass
class Capability:
    """单个能力定义"""

    name: str
    description: str
    flavor: Flavor
    dependencies: list[str]
    check_command: str  # 用于判定的 Python 表达式
    status: CapabilityStatus = CapabilityStatus.UNAVAILABLE
    details: str = ""

    def check(self) -> bool:
        """检查能力是否可用"""
        raise NotImplementedError


@dataclass
class CapabilityResult:
    """能力检查结果"""

    name: str
    status: CapabilityStatus
    flavor: Flavor
    details: str
    required_deps: list[str] = field(default_factory=list)
    missing_deps: list[str] = field(default_factory=list)


class CapabilityMatrix:
    """
    能力矩阵

    定义并检查系统能力
    """

    def __init__(self):
        self._results: dict[str, CapabilityResult] = {}
        self._flavor: Flavor = Flavor.LITE

    def check_all(self) -> dict[str, CapabilityResult]:
        """检查所有能力"""
        self._results.clear()

        # 平台适配
        self._check_platform_adapter()

        # 规则决策 (始终可用)
        self._check_rule_engine()

        # TUI (始终可用)
        self._check_tui()

        # 模板注册表 (始终可用)
        self._check_template_registry()

        # 模板匹配 (需要 cv2)
        self._check_template_matching()

        # OCR
        self._check_ocr()

        # 识别引擎 (需要模板匹配 + OCR)
        self._check_recognition_engine()

        # LLM
        self._check_llm()

        # 确定当前 flavor
        self._determine_flavor()

        return self._results

    def _check_platform_adapter(self) -> None:
        """检查平台适配器"""
        system = platform.system()

        if system == "Darwin":
            try:
                from Quartz import CGWindowListCopyWindowInfo  # noqa: F401

                status = CapabilityStatus.AVAILABLE
                details = "Mac PlayCover (Quartz)"
                missing = []
            except ImportError:
                status = CapabilityStatus.UNAVAILABLE
                details = "缺少 pyobjc-framework-Quartz"
                missing = ["pyobjc-framework-Quartz"]
        elif system == "Windows":
            try:
                from platforms.windows_emulator import WindowsEmulatorAdapter  # noqa: F401

                status = CapabilityStatus.AVAILABLE
                details = "Windows Emulator (ADB)"
                missing = []
            except ImportError:
                status = CapabilityStatus.PARTIAL
                details = "缺少 adafruit-circuitpython-adb-shell"
                missing = ["adafruit-circuitpython-adb-shell"]
        else:
            status = CapabilityStatus.UNAVAILABLE
            details = f"不支持的平台: {system}"
            missing = []

        self._results["platform_adapter"] = CapabilityResult(
            name="平台适配器",
            status=status,
            flavor=Flavor.LITE,
            details=details,
            required_deps=["mss"],
            missing_deps=missing,
        )

    def _check_rule_engine(self) -> None:
        """检查规则引擎"""
        self._results["rule_engine"] = CapabilityResult(
            name="规则决策",
            status=CapabilityStatus.AVAILABLE,
            flavor=Flavor.LITE,
            details="基于规则的快速决策",
            required_deps=["pydantic", "pyyaml"],
            missing_deps=[],
        )

    def _check_tui(self) -> None:
        """检查 TUI"""
        try:
            import rich  # noqa: F401

            status = CapabilityStatus.AVAILABLE
            missing = []
        except ImportError:
            status = CapabilityStatus.UNAVAILABLE
            missing = ["rich"]

        self._results["tui"] = CapabilityResult(
            name="终端界面",
            status=status,
            flavor=Flavor.LITE,
            details="Rich TUI 界面",
            required_deps=["rich"],
            missing_deps=missing,
        )

    def _check_template_registry(self) -> None:
        """检查模板注册表"""
        try:
            from core.vision.template_registry import TemplateRegistry

            registry = TemplateRegistry()
            count = registry.load_from_registry_json()

            if count > 0:
                status = CapabilityStatus.AVAILABLE
                details = f"已加载 {count} 个模板"
            else:
                status = CapabilityStatus.PARTIAL
                details = "注册表为空"
            missing: list[str] = []
        except Exception as e:
            status = CapabilityStatus.UNAVAILABLE
            details = str(e)
            missing = []

        self._results["template_registry"] = CapabilityResult(
            name="模板注册表",
            status=status,
            flavor=Flavor.LITE,
            details=details,
            required_deps=[],
            missing_deps=missing,
        )

    def _check_template_matching(self) -> None:
        """检查模板匹配"""
        missing = []

        try:
            import cv2  # noqa: F401

            cv2_status = True
        except ImportError:
            cv2_status = False
            missing.append("opencv-python")

        try:
            import numpy  # noqa: F401

            numpy_status = True
        except ImportError:
            numpy_status = False
            missing.append("numpy")

        if cv2_status and numpy_status:
            status = CapabilityStatus.AVAILABLE
            details = "OpenCV 模板匹配可用"
        elif missing:
            status = CapabilityStatus.UNAVAILABLE
            details = f"缺少依赖: {', '.join(missing)}"
        else:
            status = CapabilityStatus.UNAVAILABLE
            details = "未知错误"

        self._results["template_matching"] = CapabilityResult(
            name="模板匹配",
            status=status,
            flavor=Flavor.FULL,
            details=details,
            required_deps=["opencv-python", "numpy"],
            missing_deps=missing,
        )

    def _check_ocr(self) -> None:
        """检查 OCR"""
        missing = []
        engines = []

        # RapidOCR
        try:
            import rapidocr_onnxruntime  # noqa: F401

            engines.append("rapidocr")
        except ImportError:
            missing.append("rapidocr-onnxruntime")

        # Tesseract
        try:
            import pytesseract  # noqa: F401

            engines.append("tesseract")
        except ImportError:
            pass  # Optional

        if engines:
            status = CapabilityStatus.AVAILABLE
            details = f"OCR 引擎: {', '.join(engines)}"
        elif missing:
            status = CapabilityStatus.UNAVAILABLE
            details = f"缺少依赖: {', '.join(missing)}"
        else:
            status = CapabilityStatus.UNAVAILABLE
            details = "无可用的 OCR 引擎"

        self._results["ocr"] = CapabilityResult(
            name="OCR",
            status=status,
            flavor=Flavor.FULL,
            details=details,
            required_deps=["rapidocr-onnxruntime"],
            missing_deps=missing if not engines else [],
        )

    def _check_recognition_engine(self) -> None:
        """检查识别引擎"""
        template: CapabilityResult | None = self._results.get("template_matching")
        ocr: CapabilityResult | None = self._results.get("ocr")
        template_ok = template is not None and template.status == CapabilityStatus.AVAILABLE
        ocr_ok = ocr is not None and ocr.status == CapabilityStatus.AVAILABLE

        if template_ok and ocr_ok:
            status = CapabilityStatus.AVAILABLE
            details = "识别引擎完全可用 (模板+OCR)"
        elif template_ok:
            status = CapabilityStatus.PARTIAL
            details = "仅模板匹配可用"
        elif ocr_ok:
            status = CapabilityStatus.PARTIAL
            details = "仅 OCR 可用"
        else:
            status = CapabilityStatus.UNAVAILABLE
            details = "需要模板匹配和 OCR"

        self._results["recognition_engine"] = CapabilityResult(
            name="识别引擎",
            status=status,
            flavor=Flavor.FULL,
            details=details,
            required_deps=["opencv-python", "rapidocr-onnxruntime"],
            missing_deps=[],
        )

    def _check_llm(self) -> None:
        """检查 LLM"""
        available = []

        if os.getenv("ANTHROPIC_API_KEY"):
            available.append("anthropic")
        if os.getenv("OPENAI_API_KEY"):
            available.append("openai")
        if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
            available.append("gemini")

        if available:
            status = CapabilityStatus.AVAILABLE
            details = f"已配置: {', '.join(available)}"
        else:
            status = CapabilityStatus.NOT_CONFIGURED
            details = "未配置 API Key"

        self._results["llm"] = CapabilityResult(
            name="LLM 决策",
            status=status,
            flavor=Flavor.FULL,
            details=details,
            required_deps=["anthropic", "openai", "google-genai"],
            missing_deps=[],
        )

    def _determine_flavor(self) -> None:
        """确定当前 flavor"""
        # FULL 需要模板匹配 + OCR 都可用
        tm: CapabilityResult | None = self._results.get("template_matching")
        ocr: CapabilityResult | None = self._results.get("ocr")
        template_ok = tm is not None and tm.status == CapabilityStatus.AVAILABLE
        ocr_ok = ocr is not None and ocr.status == CapabilityStatus.AVAILABLE

        if template_ok and ocr_ok:
            self._flavor = Flavor.FULL
        else:
            self._flavor = Flavor.LITE

    @property
    def flavor(self) -> Flavor:
        """获取当前 flavor"""
        return self._flavor

    def is_full(self) -> bool:
        """是否为 FULL flavor"""
        return self._flavor == Flavor.FULL

    def get_summary(self) -> dict[str, Any]:
        """获取能力摘要"""
        return {
            "flavor": self._flavor.value,
            "capabilities": {
                name: {
                    "status": result.status.value,
                    "flavor": result.flavor.value,
                    "details": result.details,
                }
                for name, result in self._results.items()
            },
            "full_capabilities_available": self.is_full(),
        }

    def format_summary(self) -> str:
        """格式化能力摘要为可读字符串"""
        lines = [
            f"=== 能力矩阵 [{self._flavor.value.upper()}] ===",
            "",
        ]

        # Lite 能力
        lines.append("[Lite - 基础能力]")
        for name, result in self._results.items():
            if result.flavor == Flavor.LITE:
                icon = "✓" if result.status == CapabilityStatus.AVAILABLE else "✗"
                lines.append(f"  {icon} {result.name}: {result.details}")

        lines.append("")
        lines.append("[Full - 完整能力]")

        for name, result in self._results.items():
            if result.flavor == Flavor.FULL:
                if result.status == CapabilityStatus.AVAILABLE:
                    icon = "✓"
                elif result.status == CapabilityStatus.PARTIAL:
                    icon = "◐"
                elif result.status == CapabilityStatus.NOT_CONFIGURED:
                    icon = "◇"
                else:
                    icon = "✗"
                lines.append(f"  {icon} {result.name}: {result.details}")

        lines.append("")
        lines.append(f"当前层级: {self._flavor.value.upper()}")

        return "\n".join(lines)

    def format_summary_ascii(self) -> str:
        """Format capability summary as ASCII string (Windows cp1252 safe)"""
        lines = [
            f"=== Capability Matrix [{self._flavor.value.upper()}] ===",
            "",
        ]

        # Lite capabilities
        lines.append("[Lite - Basic]")
        for name, result in self._results.items():
            if result.flavor == Flavor.LITE:
                icon = "[OK]" if result.status == CapabilityStatus.AVAILABLE else "[X]"
                lines.append(f"  {icon} {result.name}: {result.details}")

        lines.append("")
        lines.append("[Full - Advanced]")

        for name, result in self._results.items():
            if result.flavor == Flavor.FULL:
                if result.status == CapabilityStatus.AVAILABLE:
                    icon = "[OK]"
                elif result.status == CapabilityStatus.PARTIAL:
                    icon = "[~]"
                elif result.status == CapabilityStatus.NOT_CONFIGURED:
                    icon = "[?]"
                else:
                    icon = "[X]"
                lines.append(f"  {icon} {result.name}: {result.details}")

        lines.append("")
        lines.append(f"Current tier: {self._flavor.value.upper()}")

        return "\n".join(lines)

    def check_full_requirements(self) -> tuple[bool, list[str]]:
        """
        检查 FULL flavor 的硬性要求

        包括:
        1. 可 import 关键依赖 (cv2, rapidocr_onnxruntime)
        2. 模板文件数量 > 0 且可加载
        3. OCR 后端可初始化

        Returns:
            (是否满足, 缺失列表)
        """
        missing = []

        # 1. 检查 cv2 可导入
        try:
            import cv2

            _ = cv2.__version__
        except ImportError:
            missing.append("cv2_import")

        # 2. 检查 rapidocr_onnxruntime 可导入
        try:
            from rapidocr_onnxruntime import RapidOCR

            # 尝试初始化 OCR
            _ = RapidOCR()
        except ImportError:
            missing.append("rapidocr_import")
        except Exception as e:
            missing.append(f"rapidocr_init:{str(e)[:30]}")

        # 3. 检查模板文件数量 > 0 且可加载
        try:
            from core.vision.template_registry import TemplateRegistry

            registry = TemplateRegistry()
            count = registry.load_from_registry_json()
            if count == 0:
                missing.append("templates_empty")
        except Exception as e:
            missing.append(f"templates_load:{str(e)[:30]}")

        # 4. 检查 numpy 可导入
        try:
            import numpy

            _ = numpy.__version__
        except ImportError:
            missing.append("numpy_import")

        return len(missing) == 0, missing

    def verify_full_dist_ready(self) -> tuple[bool, str]:
        """
        验证 dist 是否具备 Full 能力

        Returns:
            (是否就绪, 详细信息)
        """
        ready, missing = self.check_full_requirements()
        if ready:
            return True, "Full dist ready: all dependencies and assets available"
        else:
            return False, f"Full dist not ready: {', '.join(missing)}"


def get_capability_matrix() -> CapabilityMatrix:
    """获取能力矩阵实例"""
    matrix = CapabilityMatrix()
    matrix.check_all()
    return matrix

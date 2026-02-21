"""
视觉模块
"""

from core.vision.recognition_engine import RecognitionEngine, RecognizedEntity
from core.vision.regions import GameRegions, UIRegion, scale_regions
from core.vision.som_annotator import SoMAnnotator
from core.vision.template_registry import TemplateEntry, TemplateRegistry

__all__ = [
    "GameRegions",
    "RecognizedEntity",
    "RecognitionEngine",
    "SoMAnnotator",
    "TemplateEntry",
    "TemplateRegistry",
    "UIRegion",
    "scale_regions",
]

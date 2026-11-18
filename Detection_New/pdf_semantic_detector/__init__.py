"""Region-level PDF semantic detector for implicit prompt injection."""

from .config import DetectionConfig
from .detector import detect_pdf_implicit_injection
from .models import MappingResult, ParserSpan, RegionDescriptor, RiskFinding

__all__ = [
    "DetectionConfig",
    "MappingResult",
    "ParserSpan",
    "RegionDescriptor",
    "RiskFinding",
    "detect_pdf_implicit_injection",
]

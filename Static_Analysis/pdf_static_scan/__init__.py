"""Fast static PDF implicit-injection scanner."""

from .config import ScanConfig
from .scanner import scan_pdf, scan_pdf_multi

__all__ = ["ScanConfig", "scan_pdf", "scan_pdf_multi"]

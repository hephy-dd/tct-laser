from .rasterscan import RasterScanWidget
from .zscan import ZScanWidget

__all__ = ["operation_registry"]

operation_registry: list = [
    RasterScanWidget,
    ZScanWidget,
]

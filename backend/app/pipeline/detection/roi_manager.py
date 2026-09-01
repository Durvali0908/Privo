"""
app/pipeline/detection/roi_manager.py

Defines DetectedRegion — the normalised output of every detector.
ROIManager collects regions from all detectors into one list.

All coordinates are in pixels, origin = top-left corner.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger(__name__)


class RegionType(str, Enum):
    FACE     = "face"
    QR_CODE  = "qr_code"
    TEXT     = "text"


class DetectedRegion(BaseModel):
    """
    One detected privacy-relevant region in the image.

    x, y          → top-left corner in pixels
    width, height → bounding box dimensions in pixels
    region_type   → what was detected
    confidence    → detector confidence 0.0–1.0
    content       → decoded content for QR codes and text regions
    metadata      → additional detector-specific data
    """
    x: int
    y: int
    width: int
    height: int
    region_type: RegionType
    confidence: float = Field(ge=0.0, le=1.0)
    content: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def is_valid(self) -> bool:
        return self.width > 0 and self.height > 0


class ROIManager:
    """
    Collects DetectedRegion objects from all detectors.
    Filters invalid regions (zero-dimension boxes). Returns a filtered list.
    Deduplication (IoU-based) is deferred to the Signal Correlation Engine
    in Week 5 — overlapping cross-detector regions carry correlation value
    that must not be lost before that stage runs.
    """

    def __init__(self) -> None:
        self._regions: List[DetectedRegion] = []

    def add_regions(self, regions: List[DetectedRegion]) -> None:
        valid = [r for r in regions if r.is_valid]
        self._regions.extend(valid)
        logger.debug(
            f"ROI Manager: added {len(valid)} regions "
            f"(total={len(self._regions)})"
        )

    def get_all(self) -> List[DetectedRegion]:
        return list(self._regions)

    def get_by_type(self, region_type: RegionType) -> List[DetectedRegion]:
        return [r for r in self._regions if r.region_type == region_type]

    @property
    def total(self) -> int:
        return len(self._regions)

    def summary(self) -> Dict[str, int]:
        return {
            "faces":    len(self.get_by_type(RegionType.FACE)),
            "qr_codes": len(self.get_by_type(RegionType.QR_CODE)),
            "text":     len(self.get_by_type(RegionType.TEXT)),
            "total":    self.total,
        }
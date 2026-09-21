"""
app/pipeline/protection/text_protection.py

Applies protection to text ROIs in an OpenCV image matrix.

Two protection modes:
    redact → fill bounding box with solid black bar
    blur   → Gaussian blur over text region

Used for sensitive text (Aadhaar numbers, PAN, financial data)
and generic text regions the user wants removed.

Never raises — returns the image unchanged on any error.
"""

from enum import Enum
import numpy as np
import cv2

from app.core.logging import get_logger
from app.pipeline.detection.roi_manager import DetectedRegion

logger = get_logger(__name__)


class TextProtectionMode(str, Enum):
    REDACT = "redact"
    BLUR   = "blur"


class TextProtection:
    """
    Applies text protection to detected text regions.

    USAGE
    -----
    tp = TextProtection()
    protected_image = tp.apply(
        image=image_bgr,
        regions=text_regions,
        mode=TextProtectionMode.REDACT,
    )
    """

    def apply(
        self,
        image:   np.ndarray,
        regions: list[DetectedRegion],
        mode:    TextProtectionMode = TextProtectionMode.REDACT,
    ) -> np.ndarray:
        result = image.copy()

        for region in regions:
            try:
                result = self._protect_region(result, region, mode)
            except Exception as exc:
                logger.error(f"Text protection error on region: {exc}")

        logger.info(
            f"Text Protection: applied {mode.value} to "
            f"{len(regions)} region(s)"
        )
        return result

    def _protect_region(
        self,
        image:  np.ndarray,
        region: DetectedRegion,
        mode:   TextProtectionMode,
    ) -> np.ndarray:
        h, w = image.shape[:2]

        # Add small padding around text for clean visual redaction
        pad = 2
        x1 = max(0, region.x - pad)
        y1 = max(0, region.y - pad)
        x2 = min(w, region.x + region.width  + pad)
        y2 = min(h, region.y + region.height + pad)

        if x2 <= x1 or y2 <= y1:
            return image

        if mode == TextProtectionMode.REDACT:
            image[y1:y2, x1:x2] = 0   # solid black bar

        elif mode == TextProtectionMode.BLUR:
            roi = image[y1:y2, x1:x2]
            k   = max(21, (region.height // 2) | 1)
            image[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (k, k), 0)

        return image
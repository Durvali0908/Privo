"""
app/pipeline/protection/face_protection.py

Applies protection to face ROIs in an OpenCV image matrix.

Three protection modes:
    blur       → Gaussian blur over the face bounding box
    pixelate   → downsample + upsample to create pixel effect
    mask       → fill the bounding box with solid black

Never raises — returns the image unchanged on any error.
"""

from enum import Enum
from typing import Optional
import numpy as np
import cv2

from app.core.logging import get_logger
from app.pipeline.detection.roi_manager import DetectedRegion

logger = get_logger(__name__)


class FaceProtectionMode(str, Enum):
    BLUR      = "blur"
    PIXELATE  = "pixelate"
    MASK      = "mask"


class FaceProtection:
    """
    Applies face protection to detected face regions.

    USAGE
    -----
    fp = FaceProtection()
    protected_image = fp.apply(
        image=image_bgr,
        regions=face_regions,
        mode=FaceProtectionMode.BLUR,
    )
    """

    def apply(
        self,
        image:   np.ndarray,
        regions: list[DetectedRegion],
        mode:    FaceProtectionMode = FaceProtectionMode.BLUR,
    ) -> np.ndarray:
        result = image.copy()

        for region in regions:
            try:
                result = self._protect_region(result, region, mode)
            except Exception as exc:
                # Fail closed: an unprotected face must never pass as protected.
                logger.error(f"Face protection error on region ({exc}) — masking region instead")
                result = self._mask_fallback(result, region)

        logger.info(
            f"Face Protection: applied {mode.value} to "
            f"{len(regions)} region(s)"
        )
        return result

    def _protect_region(
        self,
        image:  np.ndarray,
        region: DetectedRegion,
        mode:   FaceProtectionMode,
    ) -> np.ndarray:
        h, w = image.shape[:2]

        x1 = max(0, region.x)
        y1 = max(0, region.y)
        x2 = min(w, region.x + region.width)
        y2 = min(h, region.y + region.height)

        if x2 <= x1 or y2 <= y1:
            return image

        roi = image[y1:y2, x1:x2]

        if mode == FaceProtectionMode.BLUR:
            # Kernel size proportional to face size — larger face = stronger blur
            k = max(51, (region.width // 5) | 1)  # must be odd
            protected = cv2.GaussianBlur(roi, (k, k), 0)

        elif mode == FaceProtectionMode.PIXELATE:
            roi_h, roi_w = roi.shape[:2]
            pixel_size = max(8, roi_w // 10)
            small = cv2.resize(
                roi,
                (max(1, roi_w // pixel_size), max(1, roi_h // pixel_size)),
                interpolation=cv2.INTER_LINEAR,
            )
            protected = cv2.resize(
                small,
                (roi_w, roi_h),
                interpolation=cv2.INTER_NEAREST,
            )

        elif mode == FaceProtectionMode.MASK:
            protected = np.zeros_like(roi)

        else:
            return image

        image[y1:y2, x1:x2] = protected
        return image

    def _mask_fallback(self, image: np.ndarray, region: DetectedRegion) -> np.ndarray:
        h, w = image.shape[:2]
        x1, y1 = max(0, region.x), max(0, region.y)
        x2, y2 = min(w, region.x + region.width), min(h, region.y + region.height)
        if x2 > x1 and y2 > y1:
            image[y1:y2, x1:x2] = 0
        return image
"""
app/pipeline/protection/document_protection.py

Applies protection to document regions (Aadhaar, PAN, passport)
identified by the Signal Classification Engine.

Uses text_regions from DetectionEngine output filtered by signal type.
Redaction is the only mode — partial masking of a government ID
leaves usable information and is not considered safe.

Never raises — returns the image unchanged on any error.
"""

import numpy as np
import cv2

from app.core.logging import get_logger
from app.pipeline.detection.roi_manager import DetectedRegion, RegionType
from app.pipeline.classification.signal_classification import (
    ClassificationResult,
    PrivacySignal,
)
from app.pipeline.classification.signal_ontology import SignalType

logger = get_logger(__name__)

# Signal types that trigger document redaction
DOCUMENT_SIGNAL_TYPES = {
    SignalType.INDIAN_ID_AADHAAR,
    SignalType.INDIAN_ID_PAN,
    SignalType.PASSPORT_INDICATOR,
    SignalType.GENERIC_DOCUMENT,
}


class DocumentProtection:
    """
    Redacts document regions when document signals are present.

    When a document signal is detected (e.g. INDIAN_ID_AADHAAR),
    ALL text regions in the image are redacted — not just the specific
    field that matched the pattern. This is because partial redaction
    of an identity document leaves the document readable.

    USAGE
    -----
    dp = DocumentProtection()
    protected_image = dp.apply(
        image=image_bgr,
        regions=detection_result.regions,
        classification=classification_result,
    )
    """

    def apply(
        self,
        image:          np.ndarray,
        regions:        list[DetectedRegion],
        classification: ClassificationResult,
    ) -> np.ndarray:

        # Check if any document signal was classified
        document_signals = [
            s for s in classification.signals
            if s.signal_type in DOCUMENT_SIGNAL_TYPES
        ]

        if not document_signals:
            logger.debug("Document Protection: no document signals — skipping")
            return image

        # Redact all text regions when a document is present
        text_regions = [
            r for r in regions
            if r.region_type == RegionType.TEXT
        ]

        if not text_regions:
            logger.debug("Document Protection: document signals found but no text regions to redact")
            return image

        result = image.copy()
        h, w = result.shape[:2]

        for region in text_regions:
            try:
                x1 = max(0, region.x - 2)
                y1 = max(0, region.y - 2)
                x2 = min(w, region.x + region.width  + 2)
                y2 = min(h, region.y + region.height + 2)

                if x2 > x1 and y2 > y1:
                    result[y1:y2, x1:x2] = 0
            except Exception as exc:
                logger.error(f"Document protection error on region: {exc}")

        logger.info(
            f"Document Protection: redacted {len(text_regions)} text region(s) "
            f"due to signals: {[s.signal_type.value for s in document_signals]}"
        )

        return result
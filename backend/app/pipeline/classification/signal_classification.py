"""
app/pipeline/classification/signal_classification.py

Converts DetectedRegions from the Detection Engine into
named PrivacySignals using rules from signal_ontology.py.

Never raises — returns ClassificationResult(success=False) on error.
"""

import re
from typing import List, Optional
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.pipeline.detection.roi_manager import DetectedRegion, RegionType
from app.pipeline.classification.signal_ontology import (
    SignalType,
    SignalCategory,
    SIGNAL_CATEGORY_MAP,
    AADHAAR_PATTERNS,
    PAN_PATTERNS,
    PASSPORT_PATTERNS,
    FINANCIAL_PATTERNS,
    QR_URL_PREFIXES,
    QR_CONTACT_PREFIXES,
)

logger = get_logger(__name__)

# Regex patterns for structured document numbers
_AADHAAR_RE = re.compile(r'\b\d{4}\s?\d{4}\s?\d{4}\b')
_PAN_RE      = re.compile(r'\b[A-Z]{5}\d{4}[A-Z]\b')


class PrivacySignal(BaseModel):
    """
    A named privacy signal derived from one or more DetectedRegions.

    signal_type : semantic identity of the signal
    category    : which exposure category it serves
    confidence  : inherited from the source detection (0.0–1.0)
    source_type : the RegionType that produced this signal
    content     : relevant extracted content (QR data, matched text)
    explanation : user-facing description of what was found
    """
    signal_type:  SignalType
    category:     SignalCategory
    confidence:   float = Field(ge=0.0, le=1.0)
    source_type:  str
    content:      Optional[str] = None
    explanation:  str


class ClassificationResult(BaseModel):
    """Output of SignalClassificationEngine.classify()."""
    success:  bool = Field(default=False)
    signals:  List[PrivacySignal] = Field(default_factory=list)
    error:    Optional[str] = None

    @property
    def total(self) -> int:
        return len(self.signals)

    def by_category(self) -> dict:
        result: dict = {}
        for s in self.signals:
            result.setdefault(s.category.value, []).append(s)
        return result


class SignalClassificationEngine:
    """
    Classifies DetectedRegions into PrivacySignals.

    USAGE
    -----
    engine = SignalClassificationEngine()
    result = engine.classify(detection_result.regions)
    """

    def classify(self, regions: List[DetectedRegion]) -> ClassificationResult:
        if not regions:
            return ClassificationResult(success=True, signals=[])

        logger.info(f"Signal Classification: classifying {len(regions)} region(s)")

        try:
            signals: List[PrivacySignal] = []

            face_regions = [r for r in regions if r.region_type == RegionType.FACE]
            qr_regions   = [r for r in regions if r.region_type == RegionType.QR_CODE]
            text_regions = [r for r in regions if r.region_type == RegionType.TEXT]

            signals.extend(self._classify_faces(face_regions))
            signals.extend(self._classify_qr(qr_regions))
            signals.extend(self._classify_text(text_regions))

            logger.info(
                f"Signal Classification: complete | "
                f"signals={len(signals)} | "
                f"categories={list({s.category.value for s in signals})}"
            )

            return ClassificationResult(success=True, signals=signals)

        except Exception as exc:
            logger.error(f"Signal Classification: error — {exc}", exc_info=True)
            return ClassificationResult(
                success=False,
                error=str(exc)
            )

    # ── FACE CLASSIFICATION ───────────────────────────────────────

    def _classify_faces(
        self, regions: List[DetectedRegion]
    ) -> List[PrivacySignal]:
        signals = []
        count = len(regions)

        if count == 0:
            return signals

        if count == 1:
            signals.append(PrivacySignal(
                signal_type=SignalType.FACE_VISIBLE,
                category=SIGNAL_CATEGORY_MAP[SignalType.FACE_VISIBLE],
                confidence=regions[0].confidence,
                source_type=RegionType.FACE.value,
                explanation="A human face is visible in this image and can be used to identify the subject.",
            ))
        else:
            signals.append(PrivacySignal(
                signal_type=SignalType.MULTIPLE_FACES,
                category=SIGNAL_CATEGORY_MAP[SignalType.MULTIPLE_FACES],
                confidence=max(r.confidence for r in regions),
                source_type=RegionType.FACE.value,
                content=f"{count} faces detected",
                explanation=f"{count} human faces are visible. Multiple identifiable individuals appear in this image.",
            ))

        return signals

    # ── QR CLASSIFICATION ─────────────────────────────────────────

    def _classify_qr(
        self, regions: List[DetectedRegion]
    ) -> List[PrivacySignal]:
        signals = []

        for region in regions:
            content = (region.content or "").strip()
            content_lower = content.lower()

            if any(content_lower.startswith(p) for p in QR_CONTACT_PREFIXES):
                signal_type = SignalType.QR_CONTACT
                explanation = "This QR code contains contact information (vCard or messaging data)."
            elif any(content_lower.startswith(p) for p in QR_URL_PREFIXES):
                signal_type = SignalType.QR_URL
                explanation = f"This QR code encodes a URL: {content[:80]}"
            else:
                signal_type = SignalType.QR_GENERIC
                explanation = "This QR code contains encoded data that may reveal personal or sensitive information."

            signals.append(PrivacySignal(
                signal_type=signal_type,
                category=SIGNAL_CATEGORY_MAP[signal_type],
                confidence=region.confidence,
                source_type=RegionType.QR_CODE.value,
                content=content or None,
                explanation=explanation,
            ))

        return signals

    # ── TEXT CLASSIFICATION ───────────────────────────────────────

    def _classify_text(
        self, regions: List[DetectedRegion]
    ) -> List[PrivacySignal]:
        """
        Classifies text regions using keyword matching and regex.
        Each region is checked independently.
        Multiple signals can be raised from different regions.
        A generic TEXT_PRESENT signal is raised only if no
        specific document/financial signal was found.
        """
        signals = []
        found_specific = False

        # Aggregate all text content for pattern matching
        all_text = " ".join(
            (r.content or "") for r in regions if r.content
        ).strip()

        if not all_text:
            return signals

        all_lower = all_text.lower()
        max_conf  = max((r.confidence for r in regions), default=0.5)

        # ── Aadhaar check ─────────────────────────────────────────
        if (
            any(p in all_lower for p in AADHAAR_PATTERNS)
            or _AADHAAR_RE.search(all_text)
        ):
            signals.append(PrivacySignal(
                signal_type=SignalType.INDIAN_ID_AADHAAR,
                category=SIGNAL_CATEGORY_MAP[SignalType.INDIAN_ID_AADHAAR],
                confidence=max_conf,
                source_type=RegionType.TEXT.value,
                explanation=(
                    "Text consistent with an Aadhaar card was detected. "
                    "This is a sensitive government identity document."
                ),
            ))
            found_specific = True

        # ── PAN check ─────────────────────────────────────────────
        if (
            any(p in all_lower for p in PAN_PATTERNS)
            or _PAN_RE.search(all_text)
        ):
            signals.append(PrivacySignal(
                signal_type=SignalType.INDIAN_ID_PAN,
                category=SIGNAL_CATEGORY_MAP[SignalType.INDIAN_ID_PAN],
                confidence=max_conf,
                source_type=RegionType.TEXT.value,
                explanation=(
                    "Text consistent with a PAN card was detected. "
                    "This is a sensitive Indian tax identity document."
                ),
            ))
            found_specific = True

        # ── Passport check ────────────────────────────────────────
        if any(p in all_lower for p in PASSPORT_PATTERNS):
            signals.append(PrivacySignal(
                signal_type=SignalType.PASSPORT_INDICATOR,
                category=SIGNAL_CATEGORY_MAP[SignalType.PASSPORT_INDICATOR],
                confidence=max_conf,
                source_type=RegionType.TEXT.value,
                explanation=(
                    "Text associated with a passport was detected. "
                    "Passport images contain highly sensitive identity information."
                ),
            ))
            found_specific = True

        # ── Financial check ───────────────────────────────────────
        if any(p in all_lower for p in FINANCIAL_PATTERNS):
            signals.append(PrivacySignal(
                signal_type=SignalType.FINANCIAL_INDICATOR,
                category=SIGNAL_CATEGORY_MAP[SignalType.FINANCIAL_INDICATOR],
                confidence=max_conf,
                source_type=RegionType.TEXT.value,
                explanation=(
                    "Financial information was detected in the image text, "
                    "such as account numbers, UPI IDs, or currency values."
                ),
            ))
            found_specific = True

        # ── Generic text fallback ─────────────────────────────────
        if not found_specific and regions:
            signals.append(PrivacySignal(
                signal_type=SignalType.TEXT_PRESENT,
                category=SIGNAL_CATEGORY_MAP[SignalType.TEXT_PRESENT],
                confidence=max_conf,
                source_type=RegionType.TEXT.value,
                content=all_text[:100] if len(all_text) > 100 else all_text,
                explanation=(
                    "Readable text was detected in this image. "
                    "Verify the text does not contain sensitive information."
                ),
            ))

        return signals
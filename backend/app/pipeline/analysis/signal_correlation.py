"""
app/pipeline/analysis/signal_correlation.py

Finds relationships between PrivacySignals from the Classification Engine.
A correlation means two or more signals together reveal more than either alone.

Examples:
    face_visible + location_exposure metadata  → identity + location combined
    indian_id_aadhaar + face_visible           → strong identity exposure
    qr_contact + text_present                  → contact information reinforced

Correlations increase the weight of the signals in risk scoring.
They do not create new signal types — they annotate existing ones.

Never raises — returns CorrelationResult(success=False) on error.
"""

from enum import Enum
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.pipeline.classification.signal_classification import (
    PrivacySignal,
    ClassificationResult,
)
from app.pipeline.classification.signal_ontology import SignalType, SignalCategory
from app.pipeline.extraction.metadata_vault import MetadataFinding, ExposureCategory

logger = get_logger(__name__)


class CorrelationType(str, Enum):
    IDENTITY_LOCATION   = "identity_location"
    IDENTITY_DOCUMENT   = "identity_document"
    CONTACT_REINFORCED  = "contact_reinforced"
    FINANCIAL_DOCUMENT  = "financial_document"
    MULTI_PERSON        = "multi_person_exposure"


class SignalCorrelation(BaseModel):
    """
    A detected relationship between two or more signals or findings.

    correlation_type : the named relationship
    signal_types     : which SignalTypes participate
    categories       : which exposure categories are affected
    weight           : multiplier applied to risk scores (1.0 = no boost)
    explanation      : user-facing description of the combined risk
    """
    correlation_type: CorrelationType
    signal_types:     List[str]
    categories:       List[str]
    weight:           float = Field(default=1.5, ge=1.0, le=3.0)
    explanation:      str


class CorrelationResult(BaseModel):
    success:      bool = Field(default=False)
    correlations: List[SignalCorrelation] = Field(default_factory=list)
    error:        Optional[str] = None


class SignalCorrelationEngine:
    """
    Analyses PrivacySignals and MetadataFindings for correlations.

    USAGE
    -----
    engine = SignalCorrelationEngine()
    result = engine.correlate(classification_result, metadata_findings)
    """

    def correlate(
        self,
        classification: ClassificationResult,
        metadata_findings: List[MetadataFinding],
    ) -> CorrelationResult:

        logger.info(
            f"Signal Correlation: analysing {len(classification.signals)} signal(s) "
            f"+ {len(metadata_findings)} metadata finding(s)"
        )

        try:
            correlations: List[SignalCorrelation] = []
            signals   = classification.signals
            signal_types = {s.signal_type for s in signals}
            meta_cats    = {f.category for f in metadata_findings}

            # ── identity + location ─────────────────────────────
            if (
                (SignalType.FACE_VISIBLE in signal_types or
                 SignalType.MULTIPLE_FACES in signal_types)
                and ExposureCategory.LOCATION in meta_cats
            ):
                correlations.append(SignalCorrelation(
                    correlation_type=CorrelationType.IDENTITY_LOCATION,
                    signal_types=[SignalType.FACE_VISIBLE.value,
                                  "location_exposure"],
                    categories=[SignalCategory.IDENTITY.value,
                                SignalCategory.CONTACT.value],
                    weight=2.0,
                    explanation=(
                        "A face is visible alongside location metadata. "
                        "Together they link an identifiable person to a specific place."
                    ),
                ))

            # ── identity + document ─────────────────────────────
            if (
                (SignalType.FACE_VISIBLE in signal_types or
                 SignalType.MULTIPLE_FACES in signal_types)
                and (
                    SignalType.INDIAN_ID_AADHAAR in signal_types or
                    SignalType.INDIAN_ID_PAN in signal_types or
                    SignalType.PASSPORT_INDICATOR in signal_types
                )
            ):
                correlations.append(SignalCorrelation(
                    correlation_type=CorrelationType.IDENTITY_DOCUMENT,
                    signal_types=[SignalType.FACE_VISIBLE.value,
                                  SignalType.INDIAN_ID_AADHAAR.value],
                    categories=[SignalCategory.IDENTITY.value,
                                SignalCategory.DOCUMENT.value],
                    weight=2.5,
                    explanation=(
                        "A face appears alongside an identity document. "
                        "This combination strongly identifies the document holder."
                    ),
                ))

            # ── contact reinforced ──────────────────────────────
            if (
                (SignalType.QR_CONTACT in signal_types or
                 SignalType.QR_URL in signal_types)
                and ExposureCategory.CONTACT in meta_cats
            ):
                correlations.append(SignalCorrelation(
                    correlation_type=CorrelationType.CONTACT_REINFORCED,
                    signal_types=[SignalType.QR_CONTACT.value, "contact_exposure"],
                    categories=[SignalCategory.CONTACT.value],
                    weight=1.5,
                    explanation=(
                        "Contact information appears in both the image QR code "
                        "and the image metadata, reinforcing the exposure."
                    ),
                ))

            # ── financial + document ────────────────────────────
            if (
                SignalType.FINANCIAL_INDICATOR in signal_types
                and (
                    SignalType.INDIAN_ID_AADHAAR in signal_types or
                    SignalType.INDIAN_ID_PAN in signal_types
                )
            ):
                correlations.append(SignalCorrelation(
                    correlation_type=CorrelationType.FINANCIAL_DOCUMENT,
                    signal_types=[SignalType.FINANCIAL_INDICATOR.value,
                                  SignalType.INDIAN_ID_PAN.value],
                    categories=[SignalCategory.FINANCIAL.value,
                                SignalCategory.DOCUMENT.value],
                    weight=2.5,
                    explanation=(
                        "Financial information and an identity document appear together. "
                        "This combination poses a high risk of financial fraud."
                    ),
                ))

            # ── multiple faces ──────────────────────────────────
            if SignalType.MULTIPLE_FACES in signal_types:
                correlations.append(SignalCorrelation(
                    correlation_type=CorrelationType.MULTI_PERSON,
                    signal_types=[SignalType.MULTIPLE_FACES.value],
                    categories=[SignalCategory.IDENTITY.value],
                    weight=1.5,
                    explanation=(
                        "Multiple people are identifiable in this image. "
                        "Sharing it affects the privacy of all visible individuals."
                    ),
                ))

            logger.info(
                f"Signal Correlation: found {len(correlations)} correlation(s)"
            )

            return CorrelationResult(success=True, correlations=correlations)

        except Exception as exc:
            logger.error(f"Signal Correlation: error — {exc}", exc_info=True)
            return CorrelationResult(success=False, error=str(exc))
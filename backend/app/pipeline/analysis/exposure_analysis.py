"""
app/pipeline/analysis/exposure_analysis.py

Maps PrivacySignals, MetadataFindings, and SignalCorrelations
into a structured ExposureAnalysis per category.

Each ExposureAnalysis represents how much evidence exists
for one of Privo's 10 official exposure categories.

Never raises — returns ExposureResult(success=False) on error.
"""

from typing import List, Dict, Optional
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.pipeline.classification.signal_classification import ClassificationResult
from app.pipeline.classification.signal_ontology import SignalCategory
from app.pipeline.extraction.metadata_vault import MetadataFinding, ExposureCategory, FindingSeverity
from app.pipeline.analysis.signal_correlation import CorrelationResult, SignalCorrelation

logger = get_logger(__name__)

# Base severity weights — used to compute raw exposure scores
SEVERITY_WEIGHT = {
    FindingSeverity.HIGH:   3.0,
    FindingSeverity.MEDIUM: 2.0,
    FindingSeverity.LOW:    1.0,
}

# Signal category → exposure category mapping
SIGNAL_TO_EXPOSURE: Dict[str, str] = {
    SignalCategory.IDENTITY.value:   ExposureCategory.IDENTITY.value,
    SignalCategory.CONTACT.value:    ExposureCategory.CONTACT.value,
    SignalCategory.DOCUMENT.value:   ExposureCategory.DOCUMENT.value,
    SignalCategory.FINANCIAL.value:  ExposureCategory.FINANCIAL.value,
    SignalCategory.ACTIVITY.value:   ExposureCategory.ACTIVITY.value,
    SignalCategory.CHILD.value:      ExposureCategory.CHILD.value,
}


class CategoryExposure(BaseModel):
    """
    Evidence summary for one exposure category.

    category        : the exposure category identifier
    raw_score       : sum of weighted evidence before correlation boost
    final_score     : raw_score × max correlation weight (capped at 10.0)
    evidence_count  : number of findings + signals contributing
    is_correlated   : whether a correlation boosted this category
    contributing_signals : signal_types and field_names that contributed
    """
    category:              str
    raw_score:             float = Field(default=0.0)
    final_score:           float = Field(default=0.0, ge=0.0, le=10.0)
    evidence_count:        int   = Field(default=0)
    is_correlated:         bool  = Field(default=False)
    contributing_signals:  List[str] = Field(default_factory=list)


class ExposureResult(BaseModel):
    success:   bool = Field(default=False)
    exposures: List[CategoryExposure] = Field(default_factory=list)
    error:     Optional[str] = None

    def get(self, category: str) -> Optional[CategoryExposure]:
        return next((e for e in self.exposures if e.category == category), None)

    def top(self, n: int = 3) -> List[CategoryExposure]:
        return sorted(self.exposures, key=lambda e: e.final_score, reverse=True)[:n]


class ExposureAnalysisEngine:
    """
    Produces a CategoryExposure for every category that has evidence.

    USAGE
    -----
    engine = ExposureAnalysisEngine()
    result = engine.analyse(
        classification_result,
        metadata_findings,
        correlation_result,
    )
    """

    def analyse(
        self,
        classification: ClassificationResult,
        metadata_findings: List[MetadataFinding],
        correlations: CorrelationResult,
    ) -> ExposureResult:

        logger.info("Exposure Analysis: starting")

        try:
            # scores[category] = (raw_score, evidence_count, signals, correlated)
            scores: Dict[str, Dict] = {}

            def add(category: str, score: float, label: str) -> None:
                if category not in scores:
                    scores[category] = {
                        "raw": 0.0, "count": 0,
                        "signals": [], "correlated": False
                    }
                scores[category]["raw"]     += score
                scores[category]["count"]   += 1
                scores[category]["signals"].append(label)

            # ── Metadata findings ───────────────────────────────
            for finding in metadata_findings:
                weight = SEVERITY_WEIGHT.get(finding.severity, 1.0)
                if finding.is_combination:
                    weight *= 1.5
                add(finding.category.value, weight, finding.field_name)

            # ── Classification signals ──────────────────────────
            for signal in classification.signals:
                exposure_cat = SIGNAL_TO_EXPOSURE.get(signal.category.value)
                if not exposure_cat:
                    continue
                # Signals start at medium weight (2.0), scaled by confidence
                weight = 2.0 * signal.confidence
                add(exposure_cat, weight, signal.signal_type.value)

            # ── Apply correlation boosts ────────────────────────
            correlated_categories: Dict[str, float] = {}
            for corr in correlations.correlations:
                for cat in corr.categories:
                    existing = correlated_categories.get(cat, 1.0)
                    correlated_categories[cat] = max(existing, corr.weight)

            # ── Build CategoryExposure objects ──────────────────
            exposures: List[CategoryExposure] = []

            for category, data in scores.items():
                raw   = data["raw"]
                boost = correlated_categories.get(category, 1.0)
                final = min(raw * boost, 10.0)

                exposures.append(CategoryExposure(
                    category=category,
                    raw_score=round(raw, 2),
                    final_score=round(final, 2),
                    evidence_count=data["count"],
                    is_correlated=boost > 1.0,
                    contributing_signals=data["signals"],
                ))

            # Sort by final_score descending
            exposures.sort(key=lambda e: e.final_score, reverse=True)

            logger.info(
                f"Exposure Analysis: {len(exposures)} category exposures | "
                f"top={exposures[0].category if exposures else 'none'}"
            )

            return ExposureResult(success=True, exposures=exposures)

        except Exception as exc:
            logger.error(f"Exposure Analysis: error — {exc}", exc_info=True)
            return ExposureResult(success=False, error=str(exc))
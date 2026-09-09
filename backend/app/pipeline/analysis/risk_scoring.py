"""
app/pipeline/analysis/risk_scoring.py

Produces a final risk score per exposure category and an overall
risk score for the image, based on ExposureAnalysis results.

Risk levels:
    0.0 – 2.9  → low
    3.0 – 5.9  → medium
    6.0 – 7.9  → high
    8.0 – 10.0 → critical

Never raises — returns RiskResult(success=False) on error.
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.pipeline.analysis.exposure_analysis import ExposureResult, CategoryExposure

logger = get_logger(__name__)

# Thresholds — adjustable without touching scoring logic
RISK_THRESHOLDS = {
    "critical": 8.0,
    "high":     6.0,
    "medium":   3.0,
    "low":      0.0,
}

# Category weights — some exposure categories carry more risk than others
CATEGORY_WEIGHTS: Dict[str, float] = {
    "identity_exposure":      1.3,
    "document_exposure":      1.5,
    "financial_exposure":     1.5,
    "child_safety_exposure":  2.0,
    "location_exposure":      1.2,
    "contact_exposure":       1.1,
    "travel_exposure":        1.1,
    "activity_exposure":      0.9,
    "educational_exposure":   0.9,
    "workplace_exposure":     1.0,
}


def _score_to_level(score: float) -> str:
    if score >= RISK_THRESHOLDS["critical"]:
        return "critical"
    if score >= RISK_THRESHOLDS["high"]:
        return "high"
    if score >= RISK_THRESHOLDS["medium"]:
        return "medium"
    return "low"


class CategoryRisk(BaseModel):
    """Risk score for one exposure category."""
    category:    str
    score:       float = Field(ge=0.0, le=10.0)
    level:       str   # "low" | "medium" | "high" | "critical"
    is_correlated: bool = False


class RiskResult(BaseModel):
    """
    Overall risk assessment for the image.

    overall_score  : weighted average of top category scores (0–10)
    overall_level  : "low" | "medium" | "high" | "critical"
    category_risks : risk per exposure category, sorted score descending
    dominant_category : the highest-scoring category
    """
    success:           bool = Field(default=False)
    overall_score:     float = Field(default=0.0, ge=0.0, le=10.0)
    overall_level:     str   = Field(default="low")
    category_risks:    List[CategoryRisk] = Field(default_factory=list)
    dominant_category: Optional[str] = None
    error:             Optional[str] = None


class RiskScoringEngine:
    """
    Computes risk scores from ExposureAnalysis results.

    USAGE
    -----
    engine = RiskScoringEngine()
    result = engine.score(exposure_result)
    """

    def score(self, exposure: ExposureResult) -> RiskResult:
        logger.info("Risk Scoring: starting")

        try:
            if not exposure.success or not exposure.exposures:
                return RiskResult(
                    success=True,
                    overall_score=0.0,
                    overall_level="low",
                )

            category_risks: List[CategoryRisk] = []

            for exp in exposure.exposures:
                weight     = CATEGORY_WEIGHTS.get(exp.category, 1.0)
                raw_score  = min(exp.final_score * weight, 10.0)

                category_risks.append(CategoryRisk(
                    category=exp.category,
                    score=round(raw_score, 2),
                    level=_score_to_level(raw_score),
                    is_correlated=exp.is_correlated,
                ))

            # Sort descending
            category_risks.sort(key=lambda r: r.score, reverse=True)

            # Overall score — weighted average of top 3 categories
            # Top category carries 50%, second 30%, third 20%
            top      = category_risks[:3]
            weights  = [0.5, 0.3, 0.2]
            overall  = sum(
                r.score * weights[i]
                for i, r in enumerate(top)
            )
            overall  = round(min(overall, 10.0), 2)

            dominant = category_risks[0].category if category_risks else None

            logger.info(
                f"Risk Scoring: complete | "
                f"overall={overall} ({_score_to_level(overall)}) | "
                f"dominant={dominant}"
            )

            return RiskResult(
                success=True,
                overall_score=overall,
                overall_level=_score_to_level(overall),
                category_risks=category_risks,
                dominant_category=dominant,
            )

        except Exception as exc:
            logger.error(f"Risk Scoring: error — {exc}", exc_info=True)
            return RiskResult(success=False, error=str(exc))
"""
app/pipeline/visualisation/heatmap_engine.py

Produces heatmap overlay data from DetectedRegions and RiskResult.

The heatmap is a list of HeatmapCell objects — each cell is a
bounding box with a heat intensity (0.0–1.0) and the signal type
that produced it.

The frontend renders these cells as semi-transparent coloured
overlays on top of the captured/selected image.

Never raises — returns HeatmapResult(success=False) on error.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.pipeline.detection.roi_manager import DetectedRegion, RegionType
from app.pipeline.analysis.risk_scoring import RiskResult
from app.pipeline.classification.signal_classification import ClassificationResult
from app.pipeline.classification.signal_ontology import SignalType

logger = get_logger(__name__)

# Heat intensity by region type — base values before risk scaling
BASE_HEAT: dict = {
    RegionType.FACE:     0.8,
    RegionType.QR_CODE:  0.7,
    RegionType.TEXT:     0.5,
}

# Risk level multipliers
RISK_MULTIPLIER: dict = {
    "critical": 1.0,
    "high":     0.85,
    "medium":   0.65,
    "low":      0.45,
}


class HeatmapCell(BaseModel):
    """
    One overlay cell in the privacy heatmap.

    x, y, width, height : pixel coordinates matching DetectedRegion
    intensity           : 0.0–1.0 — drives opacity of the overlay colour
    region_type         : "face" | "qr_code" | "text"
    signal_type         : the named signal this cell represents
    colour              : hex colour string for the frontend renderer
    """
    x:           int
    y:           int
    width:       int
    height:      int
    intensity:   float = Field(ge=0.0, le=1.0)
    region_type: str
    signal_type: str
    colour:      str   # hex e.g. "#FF6B6B"


class HeatmapResult(BaseModel):
    success:       bool = Field(default=False)
    cells:         List[HeatmapCell] = Field(default_factory=list)
    image_width:   int = Field(default=0)
    image_height:  int = Field(default=0)
    error:         Optional[str] = None


# Colour per region type — matches UI severity palette
REGION_COLOUR: dict = {
    RegionType.FACE:     "#FF6B6B",   # red — identity risk
    RegionType.QR_CODE:  "#FFB347",   # amber — contact risk
    RegionType.TEXT:     "#94A3B8",   # slate — activity/document risk
}

# Override colour for specific high-risk signal types
SIGNAL_COLOUR_OVERRIDE: dict = {
    SignalType.INDIAN_ID_AADHAAR:   "#FF2020",
    SignalType.INDIAN_ID_PAN:       "#FF2020",
    SignalType.PASSPORT_INDICATOR:  "#FF2020",
    SignalType.FINANCIAL_INDICATOR: "#FF6B6B",
    SignalType.CHILD_FACE_INDICATOR:"#FF0000",
}


class HeatmapEngine:
    """
    Produces HeatmapCell list from detected regions + risk results.

    USAGE
    -----
    engine = HeatmapEngine()
    result = engine.generate(
        regions=detection_result.regions,
        classification=classification_result,
        risk=risk_result,
        image_width=detection_result.image_width,
        image_height=detection_result.image_height,
    )
    """

    def generate(
        self,
        regions:        List[DetectedRegion],
        classification: ClassificationResult,
        risk:           RiskResult,
        image_width:    int,
        image_height:   int,
    ) -> HeatmapResult:

        logger.info(
            f"Heatmap Engine: generating from {len(regions)} region(s) | "
            f"risk={risk.overall_level}"
        )

        try:
            if not regions:
                return HeatmapResult(
                    success=True,
                    cells=[],
                    image_width=image_width,
                    image_height=image_height,
                )

            # Build a map: region_type → signal_type from classification
            signal_map: dict = {}
            for signal in classification.signals:
                rt = signal.source_type
                if rt not in signal_map:
                    signal_map[rt] = signal.signal_type

            risk_mult = RISK_MULTIPLIER.get(risk.overall_level, 0.65)
            cells: List[HeatmapCell] = []

            for region in regions:
                base_heat = BASE_HEAT.get(region.region_type, 0.5)
                intensity = round(
                    min(base_heat * risk_mult * region.confidence, 1.0), 3
                )

                # Resolve signal type for this region
                signal_type = signal_map.get(
                    region.region_type.value,
                    region.region_type.value,
                )

                # Resolve colour — signal override takes priority
                try:
                    st_enum = SignalType(signal_type)
                    colour = SIGNAL_COLOUR_OVERRIDE.get(
                        st_enum,
                        REGION_COLOUR.get(region.region_type, "#94A3B8")
                    )
                except ValueError:
                    colour = REGION_COLOUR.get(region.region_type, "#94A3B8")

                cells.append(HeatmapCell(
                    x=region.x,
                    y=region.y,
                    width=region.width,
                    height=region.height,
                    intensity=intensity,
                    region_type=region.region_type.value,
                    signal_type=str(signal_type),
                    colour=colour,
                ))

            logger.info(
                f"Heatmap Engine: generated {len(cells)} cell(s)"
            )

            return HeatmapResult(
                success=True,
                cells=cells,
                image_width=image_width,
                image_height=image_height,
            )

        except Exception as exc:
            logger.error(f"Heatmap Engine: error — {exc}", exc_info=True)
            return HeatmapResult(success=False, error=str(exc))
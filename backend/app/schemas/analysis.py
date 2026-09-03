"""
app/schemas/analysis.py

PURPOSE
-------
Defines the API response schemas for Privo's analysis endpoints.

A schema here means: the exact shape of the JSON that FastAPI
sends to the React frontend. These are the public API contracts.

─────────────────────────────────────────────────────────────────────
WHY schemas/ IS SEPARATE FROM pipeline/
─────────────────────────────────────────────────────────────────────
pipeline/ models are internal contracts between engines.
schemas/ models are external contracts with the frontend.

They can share the same field names and types, but they are separate
classes for a deliberate reason: internal models can change freely
as the pipeline evolves. The API schema should only change when the
frontend contract intentionally changes. Keeping them separate makes
breaking API changes visible and deliberate.

Example: MetadataFinding in metadata_vault.py is an internal model.
MetadataFindingSchema here is its public API representation.
In Week 2 they are identical in structure. They may diverge later.

─────────────────────────────────────────────────────────────────────
WEEK 2 ADDITIONS
─────────────────────────────────────────────────────────────────────
New schemas added:
    MetadataFindingSchema → public representation of one privacy finding
    MetadataSummary       → envelope holding findings + extraction status

Extended schema:
    AnalysisResponse      → gains one new Optional field: metadata

All Week 1 schemas are unchanged:
    SettingsSnapshot, ErrorResponse, and all existing AnalysisResponse
    fields remain exactly as they were.

─────────────────────────────────────────────────────────────────────
FULL WEEK 2 RESPONSE EXAMPLE
─────────────────────────────────────────────────────────────────────
{
    "success": true,
    "session_id": "PRIVO-SESSION-A3F8B21C",
    "filename": "photo.jpg",
    "source": "gallery",
    "status": "pending",
    "file_size_bytes": 2457600,
    "settings_loaded": true,
    "message": "photo.jpg received. Analysis pipeline ready.",
    "settings": { ... },
    "metadata": {
        "extraction_success": true,
        "total_findings": 3,
        "findings": [
            {
                "category": "location_exposure",
                "severity": "high",
                "field_name": "GPSLatitude + GPSLongitude",
                "value": "37.774900, -122.419400",
                "explanation": "This image contains GPS coordinates...",
                "is_combination": false
            },
            ...
        ]
    }
}

If extraction failed, metadata is still present but reflects failure:
    "metadata": {
        "extraction_success": false,
        "total_findings": 0,
        "findings": []
    }

If the endpoint is called from a future context where metadata has
not yet run (e.g. a status poll), metadata is null:
    "metadata": null

─────────────────────────────────────────────────────────────────────
HOW THIS FILE COMMUNICATES WITH OTHER MODULES
─────────────────────────────────────────────────────────────────────
Imported by:
    app/api/v1/endpoints/analyze.py
        → builds AnalysisResponse from SessionData +
          List[MetadataFinding] (converted to MetadataFindingSchema)

Consumed by:
    React frontend (src/types/analysis.ts)
        → TypeScript interfaces mirror these schemas exactly
        → MetadataFindingSchema → interface MetadataFinding (TS)
        → MetadataSummary       → interface MetadataSummary (TS)
        → AnalysisResponse.metadata → MetadataSummary | null

FUTURE SCHEMAS TO ADD IN THIS FILE
------------------------------------
DetectionResponse  → Week 3: detected regions and signal types
RiskResponse       → Week 4: risk scores per exposure category
HeatmapResponse    → Week 5: heatmap coordinates and overlay data
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from app.pipeline.intake.trigger import InputSource
# InputSource: enum of valid input sources (GALLERY, CAMERA, VIDEO).
# Serialised as "gallery", "camera", or "video" in the JSON response.

from app.pipeline.intake.session import SessionStatus
# SessionStatus: enum of valid session lifecycle stages.
# Serialised as "pending", "processing", "complete", or "terminated".


# ─────────────────────────────────────────────────────────────────
# WEEK 1 SCHEMAS — UNCHANGED
# ─────────────────────────────────────────────────────────────────

class SettingsSnapshot(BaseModel):
    """
    A read-only snapshot of the session settings sent to the frontend.
    Unchanged from Week 1.
    """
    theme: str = Field(description="UI theme: 'light', 'dark', or 'system'")
    scanning_mode: str = Field(description="Analysis intensity: 'fast', 'balanced', or 'thorough'")
    metadata_retention: bool = Field(description="Whether metadata is included in analysis results")
    analysis_history: bool = Field(description="Whether this session is stored in analysis history")
    cloud_processing: bool = Field(description="Whether cloud AI processing is enabled")


class ErrorResponse(BaseModel):
    """
    The JSON body inside FastAPI's HTTPException detail wrapper
    for failed requests.

    React reads this as: response.detail.error_code, response.detail.message
    The outer { "detail": ... } wrapper is added by FastAPI automatically.
    Unchanged from Week 1.
    """
    success: bool = Field(default=False)
    error_code: str = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable error message for display")
    detail: Optional[str] = Field(default=None, description="Optional diagnostic context")


# ─────────────────────────────────────────────────────────────────
# WEEK 2 ADDITIONS — METADATA SCHEMAS
# ─────────────────────────────────────────────────────────────────

class MetadataFindingSchema(BaseModel):
    """
    Public API representation of one privacy finding from MetadataVault.

    WHY NOT IMPORT MetadataFinding FROM metadata_vault.py DIRECTLY?
    ---------------------------------------------------------------
    MetadataFinding in metadata_vault.py is an internal pipeline model
    that uses ExposureCategory and FindingSeverity enums from that file.
    This schema uses plain strings for category and severity so the API
    response is clean JSON without enum class references.

    In Week 2 the fields are identical in both models.
    If the internal model gains fields that should not be in the API
    (e.g. internal scoring weights), this schema stays unchanged.

    FIELDS
    ------
    category : str
        Exposure category as a string: "location_exposure",
        "identity_exposure", "activity_exposure", etc.
        Matches ExposureCategory enum values from metadata_vault.py.

    severity : str
        Severity level as a string: "low", "medium", "high".
        Matches FindingSeverity enum values from metadata_vault.py.

    field_name : str
        The metadata field(s) that produced this finding.
        Examples: "GPSLatitude + GPSLongitude", "Make + Model"

    value : str
        The actual metadata value, formatted for display.

    explanation : str
        Non-technical explanation for the end user.

    is_combination : bool
        True when this finding was raised by two or more fields together.
    """
    category: str = Field(description="Exposure category identifier")
    severity: str = Field(description="Finding severity: 'low', 'medium', or 'high'")
    field_name: str = Field(description="Metadata field(s) that produced this finding")
    value: str = Field(description="Formatted metadata value for display")
    explanation: str = Field(description="Non-technical explanation for the user")
    is_combination: bool = Field(
        default=False,
        description="True when raised by multiple fields together"
    )


class MetadataSummary(BaseModel):
    """
    Envelope for metadata extraction and classification results.

    WHY AN ENVELOPE INSTEAD OF JUST List[MetadataFindingSchema]?
    -------------------------------------------------------------
    The frontend needs two pieces of information beyond the findings list:

    1. extraction_success: did the extraction process work?
       If False, the frontend can show "metadata could not be read"
       rather than silently showing zero findings (which would imply
       the image has clean metadata when in fact extraction failed).

    2. total_findings: the count without requiring the frontend to
       measure the list length. Convenient for UI badges and summaries.

    FIELDS
    ------
    extraction_success : bool
        True if ExifTool ran without error, regardless of finding count.
        False if ExifTool was not found, timed out, or output was invalid.
        Mirrors RawMetadata.extraction_success semantics exactly.

    total_findings : int
        len(findings). Provided as a convenience field.
        The frontend can display "3 privacy concerns found" without
        iterating the list.

    findings : List[MetadataFindingSchema]
        The complete list of privacy findings from the Metadata Vault.
        Empty when extraction failed or the image has clean metadata.
        The frontend must use extraction_success to distinguish these
        two cases when total_findings is 0.
    """
    extraction_success: bool = Field(
        description=(
            "True if ExifTool ran without error. "
            "False indicates an extraction process failure, not clean metadata."
        )
    )
    total_findings: int = Field(
        description="Total number of privacy findings found"
    )
    findings: List[MetadataFindingSchema] = Field(
        description="Privacy findings from metadata classification"
    )


# ─────────────────────────────────────────────────────────────────
# ANALYSIS RESPONSE — EXTENDED WITH METADATA
# ─────────────────────────────────────────────────────────────────

class AnalysisResponse(BaseModel):
    """
    The complete JSON response for a successful POST /api/v1/analyze.

    WEEK 2 CHANGE
    -------------
    One new optional field added: metadata.
    All Week 1 fields are unchanged.

    WHY Optional[MetadataSummary] AND NOT MetadataSummary?
    -------------------------------------------------------
    Optional means the field can be null in the JSON response.
    This handles two future cases cleanly:

    Case 1 — Week 2 analyze endpoint:
        metadata is always populated (extraction runs every request).

    Case 2 — Future session status endpoint:
        GET /api/v1/session/{id}/status may reuse AnalysisResponse.
        If the client polls before extraction completes, metadata=null
        is a valid and honest response.

    Case 3 — Future async pipeline:
        If the pipeline becomes async (extraction runs in background),
        metadata=null on the first response, populated on a later poll.

    Making it Optional now costs nothing and prevents a future
    breaking change to the schema.

    FIELD ORDER
    -----------
    Fields are ordered to match the JSON response the frontend reads:
    identity fields first, then pipeline status, then content.
    """

    # ── IDENTITY ──────────────────────────────────────────────────
    success: bool = Field(description="Always true for this response type")

    session_id: str = Field(
        description="Unique session identifier, e.g. PRIVO-SESSION-A3F8B21C"
    )

    filename: Optional[str] = Field(
        default=None,
        description="Original filename, null for camera/video sources"
    )

    source: InputSource = Field(
        description="Input source: 'gallery', 'camera', or 'video'"
    )

    # ── PIPELINE STATUS ───────────────────────────────────────────
    status: SessionStatus = Field(
        description="Current session lifecycle status"
    )

    file_size_bytes: Optional[int] = Field(
        default=None,
        description="File size in bytes, null if unavailable"
    )

    settings_loaded: bool = Field(
        description="Confirms default settings were loaded for this session"
    )

    message: str = Field(
        description="Human-readable status message"
    )

    # ── SETTINGS ──────────────────────────────────────────────────
    settings: SettingsSnapshot = Field(
        description="Settings applied to this analysis session"
    )

    # ── WEEK 2 ────────────────────────────────────────────────────
    metadata: Optional[MetadataSummary] = Field(
        default=None,
        description=(
            "Metadata extraction and classification results. "
            "Null when metadata extraction has not yet run for this session."
        )
    )

    # ── WEEK 3 ────────────────────────────────────────────────────
    detection: Optional["DetectionSummary"] = Field(
        default=None,
        description=(
            "Detection engine results. "
            "Null when detection has not yet run for this session."
        )
    )

    # ── WEEK 4 ────────────────────────────────────────────────────
    classification: Optional["ClassificationSummary"] = Field(
        default=None,
        description=(
            "Signal classification results. "
            "Null when classification has not yet run."
        )
    )

# ─────────────────────────────────────────────────────────────────
# WEEK 3 — DETECTION SCHEMAS
# ─────────────────────────────────────────────────────────────────

class DetectedRegionSchema(BaseModel):
    """
    Public API representation of one detected region.
    Mirrors DetectedRegion from roi_manager.py using plain types.
    """
    x: int
    y: int
    width: int
    height: int
    region_type: str        # "face" | "qr_code" | "text"
    confidence: float
    content: Optional[str] = None


class DetectionSummary(BaseModel):
    """
    Envelope for detection engine results.
    Mirrors DetectionResult from detection_engine.py.

    success=False means the engine could not run (not that nothing was found).
    face_count=0 with success=True means no faces detected — valid result.
    """
    success: bool
    image_width: int = Field(default=0)
    image_height: int = Field(default=0)
    face_count: int = Field(default=0)
    qr_count: int = Field(default=0)
    text_count: int = Field(default=0)
    total_regions: int = Field(default=0)
    regions: List[DetectedRegionSchema] = Field(default_factory=list)
    error: Optional[str] = None



# ─────────────────────────────────────────────────────────────────
# WEEK 4 — CLASSIFICATION SCHEMAS
# ─────────────────────────────────────────────────────────────────

class PrivacySignalSchema(BaseModel):
    """
    Public API representation of one classified privacy signal.
    Mirrors PrivacySignal from signal_classification.py.
    """
    signal_type:  str   # e.g. "face_visible", "indian_id_aadhaar"
    category:     str   # e.g. "identity_exposure"
    confidence:   float
    source_type:  str   # "face" | "qr_code" | "text"
    content:      Optional[str] = None
    explanation:  str


class ClassificationSummary(BaseModel):
    """
    Envelope for signal classification results.
    Mirrors ClassificationResult from signal_classification.py.

    success=False means the engine could not run.
    total=0 with success=True means no signals classified — valid result.
    """
    success:  bool
    total:    int = Field(default=0)
    signals:  List[PrivacySignalSchema] = Field(default_factory=list)
    error:    Optional[str] = None


# Rebuild AnalysisResponse to pick up all forward references
AnalysisResponse.model_rebuild()
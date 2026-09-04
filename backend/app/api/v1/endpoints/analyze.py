"""
app/api/v1/endpoints/analyze.py

PURPOSE
-------
The analyze endpoint — the primary HTTP route for Privo's analysis pipeline.

Receives an image from React, runs it through the pipeline,
and returns a structured JSON response.

─────────────────────────────────────────────────────────────────────
WEEK 2 CHANGES FROM WEEK 1
─────────────────────────────────────────────────────────────────────
1. Import paths updated:
       app.engine.trigger → app.pipeline.intake.trigger
       app.engine.session → app.pipeline.intake.session

2. Two new imports:
       MetadataExtractor from pipeline.extraction.metadata_extractor
       MetadataVault     from pipeline.extraction.metadata_vault

3. Two new dependency factories:
       get_metadata_extractor() → MetadataExtractor
       get_metadata_vault()     → MetadataVault

4. Three new steps in the endpoint body (Steps 3, 4, 5):
       Step 3: MetadataExtractor.extract(session.privo_frame)
       Step 4: MetadataVault.classify(raw_metadata)
       Step 5: SessionManager.update_metadata_findings(session_id, findings_dicts)

5. AnalysisResponse now includes the metadata field (Step 6).

All Week 1 logic is unchanged — validation, session creation,
error handling patterns, dependency injection pattern, response
construction for all Week 1 fields.

─────────────────────────────────────────────────────────────────────
WEEK 2 PIPELINE ORDER
─────────────────────────────────────────────────────────────────────
Step 1: TriggerEngine.validate_upload(file)
        → validates input, produces PrivoFrame
        → failure: return 400

Step 2: SessionManager.create_session(privo_frame)
        → creates session, loads default settings
        → failure: return 500

Step 3: MetadataExtractor.extract(session.privo_frame)
        → runs ExifTool, returns RawMetadata
        → never raises: returns RawMetadata(extraction_success=False) on error
        → pipeline always continues regardless of outcome

Step 4: MetadataVault.classify(raw_metadata)
        → classifies fields into List[MetadataFinding]
        → returns empty list if extraction_success is False
        → never raises

Step 5: SessionManager.update_metadata_findings(session_id, findings_dicts)
        → stores findings on the session for future engines to read
        → serialises MetadataFinding objects to dicts via .model_dump()

Step 6: Build AnalysisResponse with all fields including metadata
        → return HTTP 200

─────────────────────────────────────────────────────────────────────
PIPELINE ORCHESTRATION NOTE (carried forward from Week 1)
─────────────────────────────────────────────────────────────────────
The endpoint currently orchestrates Steps 1–5 directly. This is
appropriate for two pipeline steps (Week 1) and five steps (Week 2).

When the pipeline reaches three or more sequential engine calls
beyond the current five, extract a dedicated orchestrator:

    app/pipeline/orchestrator.py → class PrivoPipeline
        async def run(privo_frame: PrivoFrame) -> PipelineResult

Do not build this now. Build it when the pipeline needs it.

─────────────────────────────────────────────────────────────────────
HOW THIS FILE COMMUNICATES WITH OTHER MODULES
─────────────────────────────────────────────────────────────────────
Calls:
    app/pipeline/intake/trigger.py    → TriggerEngine.validate_upload()
    app/pipeline/intake/session.py    → SessionManager.create_session()
                                        SessionManager.update_metadata_findings()
    app/pipeline/extraction/
        metadata_extractor.py         → MetadataExtractor.extract()
        metadata_vault.py             → MetadataVault.classify()

Returns:
    app/schemas/analysis.py           → AnalysisResponse (HTTP 200)
                                        ErrorResponse in HTTPException (400/500)
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request

# UPDATED IMPORT PATHS (Week 2 migration: app.engine → app.pipeline.intake)
from app.pipeline.intake.trigger import TriggerEngine, InputSource
from app.pipeline.intake.session import SessionManager

# NEW WEEK 2 IMPORTS
from app.pipeline.extraction.metadata_extractor import MetadataExtractor
from app.pipeline.extraction.metadata_vault import MetadataVault

from app.schemas.analysis import (
    AnalysisResponse,
    ErrorResponse,
    SettingsSnapshot,
    MetadataFindingSchema,
    MetadataSummary,
    DetectedRegionSchema,
    DetectionSummary,
    PrivacySignalSchema,
    ClassificationSummary,
)

from app.pipeline.detection.detection_engine import DetectionEngine
from app.pipeline.detection.roi_manager import RegionType
from app.pipeline.classification.signal_classification import SignalClassificationEngine

from app.core.logging import get_logger

logger = get_logger(__name__)
# Logger name = "privo.app.api.v1.endpoints.analyze"

router = APIRouter()


# ─────────────────────────────────────────────────────────────────
# DEPENDENCY FACTORIES
# ─────────────────────────────────────────────────────────────────

def get_trigger_engine() -> TriggerEngine:
    """Dependency factory for TriggerEngine."""
    return TriggerEngine()


def get_session_manager() -> SessionManager:
    """Dependency factory for SessionManager."""
    return SessionManager()


def get_metadata_extractor() -> MetadataExtractor:
    """
    Dependency factory for MetadataExtractor.

    A new instance per request is correct — MetadataExtractor holds
    no state between requests. All state lives in the temp file it
    creates and deletes within a single extract() call.
    """
    return MetadataExtractor()


def get_metadata_vault() -> MetadataVault:
    """
    Dependency factory for MetadataVault.

    A new instance per request is correct — MetadataVault holds
    no state. All classification logic is stateless.
    """
    return MetadataVault()


# ─────────────────────────────────────────────────────────────────
# ANALYZE ENDPOINT
# POST /api/v1/analyze
# ─────────────────────────────────────────────────────────────────

@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    summary="Upload an image for privacy analysis",
    description=(
        "Accepts an image file upload, validates it, creates an analysis "
        "session, extracts and classifies metadata, and returns a structured "
        "response including privacy findings from the image's metadata."
    ),
    tags=["Analysis"]
)
async def analyze(
    request: Request,
    file: UploadFile = File(..., description="Image file to analyse"),
    engine: TriggerEngine = Depends(get_trigger_engine),
    session_manager: SessionManager = Depends(get_session_manager),
    extractor: MetadataExtractor = Depends(get_metadata_extractor),
    vault: MetadataVault = Depends(get_metadata_vault),
) -> AnalysisResponse:
    """
    Primary analysis endpoint — Week 2 pipeline orchestrator.

    PIPELINE: validate → session → extract metadata → classify → respond

    PARAMETERS
    ----------
    file : UploadFile
        The uploaded image. Required — FastAPI returns 422 if absent.

    engine : TriggerEngine
        Injected via Depends(get_trigger_engine).

    session_manager : SessionManager
        Injected via Depends(get_session_manager).

    extractor : MetadataExtractor
        Injected via Depends(get_metadata_extractor).

    vault : MetadataVault
        Injected via Depends(get_metadata_vault).

    RETURNS
    -------
    AnalysisResponse — HTTP 200 always when pipeline completes.
    Metadata extraction failure does not cause an error response —
    the pipeline degrades gracefully and metadata.extraction_success
    reflects the outcome.

    ERROR RESPONSES
    ---------------
    HTTP 400 — validation failure (bad file type, too large, etc.)
    HTTP 500 — unexpected crash in TriggerEngine or SessionManager

    Note: MetadataExtractor and MetadataVault failures are NOT 500
    errors. They return graceful results and the response is still
    HTTP 200 with metadata.extraction_success=False.
    """

    logger.info(f"Analyze endpoint: request received for '{file.filename}'")

    # ── STEP 1: Trigger Engine Validation ─────────────────────────
    try:
        validation_result = await engine.validate_upload(file)
    except Exception as exc:
        logger.error(
            f"Analyze endpoint: Trigger Engine raised an exception — {exc}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error_code="TRIGGER_ENGINE_ERROR",
                message="An unexpected error occurred during file validation. Please try again.",
                detail=None
            ).model_dump()
        )

    # ── STEP 2a: Handle Validation Failure ────────────────────────
    if not validation_result.valid:
        logger.warning(
            f"Analyze endpoint: validation failed | "
            f"code={validation_result.error_code} | "
            f"file='{file.filename}'"
        )
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error_code=validation_result.error_code or "VALIDATION_FAILED",
                message=validation_result.error_message or "File validation failed.",
                detail=None
            ).model_dump()
        )

    # ── STEP 2b: Session Creation ──────────────────────────────────
    try:
        session = session_manager.create_session(validation_result.privo_frame)
    except Exception as exc:
        logger.error(
            f"Analyze endpoint: Session Manager raised an exception — {exc}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error_code="SESSION_CREATION_ERROR",
                message="An unexpected error occurred while creating your session. Please try again.",
                detail=None
            ).model_dump()
        )

    # ── STEP 3: Metadata Extraction ───────────────────────────────
    # MetadataExtractor.extract() never raises.
    # On any internal failure it returns RawMetadata(extraction_success=False).
    # The pipeline always continues — metadata failure is non-fatal.
    raw_metadata = extractor.extract(session.privo_frame)
    # We use session.privo_frame rather than validation_result.privo_frame.
    # Both reference the same PrivoFrame object. Using session.privo_frame
    # is semantically correct: by this point the frame belongs to the session.
    # If the Session Manager ever pre-processes the frame in the future,
    # session.privo_frame will reflect that; validation_result.privo_frame
    # would not.

    logger.info(
        f"Analyze endpoint: metadata extraction done | "
        f"session={session.session_id} | "
        f"success={raw_metadata.extraction_success} | "
        f"exiftool_fields={raw_metadata.field_count}"
    )

    # ── STEP 4: Metadata Classification ───────────────────────────
    # MetadataVault.classify() never raises.
    # Returns an empty list if raw_metadata.extraction_success is False.
    findings = vault.classify(raw_metadata)

    logger.info(
        f"Analyze endpoint: metadata classification done | "
        f"session={session.session_id} | "
        f"findings={len(findings)}"
    )

    # ── STEP 5: Store Findings on Session ─────────────────────────
    # Serialise MetadataFinding objects to plain dicts for storage.
    # SessionData.metadata_findings is List[dict] — see session.py
    # for the explanation of why dict is used instead of the typed model.
    findings_dicts = [f.model_dump() for f in findings]
    # model_dump(): converts a Pydantic model instance to a plain dict.
    # ExposureCategory and FindingSeverity str enums serialise to their
    # string values: "location_exposure", "high", etc.

    stored = session_manager.update_metadata_findings(session.session_id, findings_dicts)
    if not stored:
        logger.warning(
            f"Analyze endpoint: metadata findings could not be stored — "
            f"session '{session.session_id}' not found in store. "
            f"Findings will appear in this response but are not persisted."
        )

    # ── STEP 6: Detection Engine ──────────────────────────────────
    detection_engine = DetectionEngine()
    detection_result = detection_engine.detect(
        frame=session.privo_frame,
        face_mesh=getattr(request.app.state, "face_mesh", None),
        ocr_enabled=True,
    )

    logger.info(
        f"Analyze endpoint: detection done | "
        f"session={session.session_id} | "
        f"success={detection_result.success} | "
        f"faces={detection_result.face_count} | "
        f"qr={detection_result.qr_count} | "
        f"text={detection_result.text_count} | "
        f"signals={classification_result.total}"
    )

    # ── STEP 7: Signal Classification ────────────────────────────
    classification_engine = SignalClassificationEngine()
    classification_result = classification_engine.classify(detection_result.regions)

    logger.info(
        f"Analyze endpoint: classification done | "
        f"session={session.session_id} | "
        f"signals={classification_result.total}"
    )

    # ── STEP 8: Build the API Response ────────────────────────────
    # Construct MetadataSummary from extraction results.
    metadata_summary = MetadataSummary(
        extraction_success=raw_metadata.extraction_success,
        total_findings=len(findings),
        findings=[
            MetadataFindingSchema(
                category=f.category.value,
                # .value: converts ExposureCategory enum to its str value.
                # ExposureCategory.LOCATION.value → "location_exposure"
                # MetadataFindingSchema.category is str — not the enum type.
                severity=f.severity.value,
                # FindingSeverity.HIGH.value → "high"
                field_name=f.field_name,
                value=f.value,
                explanation=f.explanation,
                is_combination=f.is_combination,
            )
            for f in findings
            # List comprehension: converts each MetadataFinding (internal model)
            # to MetadataFindingSchema (public API schema) one by one.
        ]
    )

    detection_summary = DetectionSummary(
        success=detection_result.success,
        image_width=detection_result.image_width,
        image_height=detection_result.image_height,
        face_count=detection_result.face_count,
        qr_count=detection_result.qr_count,
        text_count=detection_result.text_count,
        total_regions=len(detection_result.regions),
        regions=[
            DetectedRegionSchema(
                x=r.x,
                y=r.y,
                width=r.width,
                height=r.height,
                region_type=r.region_type.value,
                confidence=r.confidence,
                content=r.content,
            )
            for r in detection_result.regions
        ],
        error=detection_result.error,
    )

    classification_summary = ClassificationSummary(
        success=classification_result.success,
        total=classification_result.total,
        signals=[
            PrivacySignalSchema(
                signal_type=s.signal_type.value,
                category=s.category.value,
                confidence=s.confidence,
                source_type=s.source_type,
                content=s.content,
                explanation=s.explanation,
            )
            for s in classification_result.signals
        ],
        error=classification_result.error,
    )

    response = AnalysisResponse(
        success=True,
        session_id=session.session_id,
        filename=session.privo_frame.filename,
        source=session.source,
        status=session.status,
        file_size_bytes=session.privo_frame.size_bytes,
        settings_loaded=session.settings_loaded,
        message=_build_success_message(session.source, session.privo_frame.filename),
        settings=SettingsSnapshot(
            theme=session.settings.theme,
            scanning_mode=session.settings.scanning_mode,
            metadata_retention=session.settings.metadata_retention,
            analysis_history=session.settings.analysis_history,
            cloud_processing=session.settings.cloud_processing,
        ),
        metadata=metadata_summary,
        detection=detection_summary,
        classification=classification_summary,
    )

    logger.info(
        f"Analyze endpoint: response ready | "
        f"session={session.session_id} | "
        f"source={session.source.value} | "
        f"findings={len(findings)} | "
        f"extraction_success={raw_metadata.extraction_success} | "
        f"faces={detection_result.face_count} | "
        f"qr={detection_result.qr_count} | "
        f"text={detection_result.text_count} | "
        f"signals={classification_result.total}"
    )

    return response


# ─────────────────────────────────────────────────────────────────
# PRIVATE HELPERS
# ─────────────────────────────────────────────────────────────────

def _build_success_message(source: InputSource, filename) -> str:
    """
    Returns a source-aware success message for the frontend.
    Unchanged from Week 1.
    """
    if source == InputSource.GALLERY:
        display_name = filename if filename else "Image"
        return f"{display_name} received. Analysis pipeline ready."
    elif source == InputSource.CAMERA:
        return "Camera frame received. Analysis pipeline ready."
    elif source == InputSource.VIDEO:
        return "Video frame received. Analysis pipeline ready."
    else:
        return "Input received. Analysis pipeline ready."
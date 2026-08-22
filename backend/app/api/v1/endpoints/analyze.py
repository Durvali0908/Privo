"""
backend/app/api/v1/endpoints/analyze.py

PURPOSE
-------
The analyze endpoint is the primary HTTP route for Privo's analysis pipeline.

It receives an image from the React frontend, passes it through the
Trigger Engine for validation, creates a session via the Session Manager,
and returns a structured JSON response.

This file is the orchestrator of Week 1's pipeline — it calls every
backend module we have built so far and assembles their outputs into
a single cohesive response.

─────────────────────────────────────────────────────────────────────
HTTP CONTRACT
─────────────────────────────────────────────────────────────────────
Request:
    POST /api/v1/analyze
    Content-Type: multipart/form-data
    Body: { file: <image file> }

Success Response — HTTP 200:
    Content-Type: application/json
    Body: AnalysisResponse (see schemas/analysis.py)

    {
        "success": true,
        "session_id": "PRIVO-SESSION-A3F8B21C",
        "filename": "photo.jpg",
        "source": "gallery",
        "status": "pending",
        "file_size_bytes": 2457600,
        "settings_loaded": true,
        "message": "photo.jpg received. Analysis pipeline ready.",
        "settings": { ... }
    }

Error Response — HTTP 400 / 500:
    Content-Type: application/json

    FastAPI's HTTPException wraps the error body inside a "detail" key.
    React must read error.detail, not the root body.

    {
        "detail": {
            "success": false,
            "error_code": "FILE_TOO_LARGE",
            "message": "File is 45.2 MB. Maximum allowed size is 20 MB.",
            "detail": null
        }
    }

    WHY THE "detail" WRAPPER?
    --------------------------
    FastAPI's HTTPException always produces:
        { "detail": <whatever you pass as detail> }
    This is FastAPI's built-in behaviour and cannot be changed without
    a custom exception handler.

    Week 1 accepts this wrapper. React reads: error.detail.error_code.

    FUTURE — Custom Exception Handler (main.py, Week 2+):
    A custom exception handler registered in main.py can intercept
    HTTPException and return a flat ErrorResponse body without the
    "detail" wrapper. That change belongs in main.py, not here. When
    it is added, this docstring and the React api.ts client must be
    updated together.

─────────────────────────────────────────────────────────────────────
PIPELINE ORCHESTRATION — WEEK 1 VS FUTURE
─────────────────────────────────────────────────────────────────────
In Week 1 the pipeline has two steps:
    TriggerEngine.validate_upload() → SessionManager.create_session()

The endpoint orchestrates these directly. This is appropriate now.

As the pipeline grows (Metadata Extractor, Detection Engine, Risk
Scoring, Heatmap), calling every engine inline inside the endpoint
will make this function unreadable and hard to test.

WHEN TO EXTRACT A PIPELINE LAYER:
When the pipeline reaches three or more sequential engine calls,
extract a dedicated orchestrator:

    app/engine/pipeline.py → class PrivoPipeline
        def run(privo_frame: PrivoFrame) -> PipelineResult:
            session   = self.session_manager.create_session(privo_frame)
            metadata  = self.metadata_extractor.extract(session)
            detections = self.detection_engine.detect(session)
            risk      = self.risk_scoring_engine.score(session)
            return PipelineResult(session, detections, risk)

The endpoint then becomes:
    result = await pipeline.run(validation_result.privo_frame)
    return AnalysisResponse.from_result(result)

Do not build this now. Build it when the pipeline needs it.

─────────────────────────────────────────────────────────────────────
HOW THIS FILE COMMUNICATES WITH OTHER MODULES
─────────────────────────────────────────────────────────────────────
Receives from:
    React frontend
        → UploadFile via multipart/form-data POST request

Calls:
    app/engine/trigger.py  → TriggerEngine.validate_upload()
    app/engine/session.py  → SessionManager.create_session()

Returns:
    app/schemas/analysis.py → AnalysisResponse (HTTP 200)
    app/schemas/analysis.py → ErrorResponse inside HTTPException detail
                              (HTTP 400 / 500)

Mounted by:
    app/api/v1/router.py → includes this router at /analyze
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
# APIRouter: Groups related routes. This file's router is mounted
#   in router.py — it does not register directly on the FastAPI app.
#   Prefix ("/analyze") is defined in router.py, not here.
#
# UploadFile: FastAPI's file upload type. Provides:
#   .filename    → original filename from the client
#   .size        → byte count from Content-Length header (may be None)
#   .content_type→ MIME type from the client (not verified)
#   await .read()→ reads full file bytes from the HTTP stream
#   await .seek()→ resets read cursor to a given position
#
# File: Parameter descriptor for file upload fields.
#   File(...) means the field is required. FastAPI enforces this
#   before the endpoint function is called — a missing file field
#   returns 422 Unprocessable Entity automatically.
#
# HTTPException: Raises an HTTP error response.
#   FastAPI catches it and returns:
#       { "detail": <whatever you pass> }
#   with the specified status code.
#   See the HTTP CONTRACT section above for how React reads this.
#
# Depends: FastAPI's dependency injection system.
#   Depends(factory_fn) tells FastAPI to call factory_fn before
#   calling the endpoint, and pass the result as the parameter.
#   This enables replacing dependencies with mocks in tests without
#   modifying the endpoint function.

from app.pipeline.intake.trigger import TriggerEngine, InputSource
# TriggerEngine: Validates the uploaded file, returns ValidationResult.
#   validate_upload() is async — it calls await file.read() internally.
#
# InputSource: Enum of valid input sources (GALLERY, CAMERA, VIDEO).
#   Imported at module level for use in _build_success_message().
#   There is no circular import risk — trigger.py does not import
#   anything from this file.

from app.pipeline.intake.session import SessionManager
# SessionManager: Creates and stores analysis sessions.
#   create_session() is synchronous — session data is already in memory.
#   Returns SessionData containing session_id, settings, timestamps.

from app.schemas.analysis import AnalysisResponse, ErrorResponse, SettingsSnapshot
# AnalysisResponse: Pydantic schema for HTTP 200 responses.
#   Declared as response_model in the route decorator.
#   FastAPI validates and serialises the return value against this schema.
#
# ErrorResponse: Pydantic schema for error information.
#   Passed as the detail argument to HTTPException.
#   React reads it as response.detail (not response directly).
#
# SettingsSnapshot: JSON-safe representation of session settings.
#   Embedded inside AnalysisResponse.settings.

from app.core.logging import get_logger
# get_logger: Logging factory. Returns a named logger.

logger = get_logger(__name__)
# __name__ = "app.api.v1.endpoints.analyze"
# Logger name = "privo.app.api.v1.endpoints.analyze"


# ─────────────────────────────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────────────────────────────

router = APIRouter()
# No prefix here. The prefix "/analyze" is added when this router
# is included in the v1 router (router.py). Keeping prefix out of
# this file means it can be remounted at a different path without
# touching endpoint code.


# ─────────────────────────────────────────────────────────────────
# DEPENDENCY FACTORIES
# ─────────────────────────────────────────────────────────────────

def get_trigger_engine() -> TriggerEngine:
    """
    Dependency factory for TriggerEngine.

    FastAPI calls this function automatically before calling the endpoint,
    and passes the returned TriggerEngine as the `engine` parameter.

    WHY Depends() AND NOT TriggerEngine() INLINE?
    ----------------------------------------------
    Writing TriggerEngine() directly inside the endpoint couples the
    endpoint to a specific implementation. In tests, you cannot replace
    it without modifying the endpoint.

    With Depends(get_trigger_engine), you override it in tests:

        app.dependency_overrides[get_trigger_engine] = lambda: MockEngine()
        client = TestClient(app)
        # endpoint now receives MockEngine instead of TriggerEngine

    The endpoint function itself never changes. This is Inversion of
    Control: the endpoint declares what it needs, not how to create it.
    """
    return TriggerEngine()


def get_session_manager() -> SessionManager:
    """
    Dependency factory for SessionManager.

    Creating a new SessionManager() per request is intentional and cheap.
    SessionManager uses a class-level _store dict shared across all
    instances — a new instance does not create a new empty store.
    """
    return SessionManager()


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
        "session, and returns session information with loaded settings. "
        "This is the entry point to Privo's privacy analysis pipeline."
    ),
    tags=["Analysis"]
)
async def analyze(
    file: UploadFile = File(..., description="Image file to analyse"),
    engine: TriggerEngine = Depends(get_trigger_engine),
    session_manager: SessionManager = Depends(get_session_manager)
) -> AnalysisResponse:
    """
    Primary analysis endpoint — Week 1 pipeline orchestrator.

    PIPELINE (Week 1):
        1. Trigger Engine validates the uploaded file
        2. Session Manager creates an analysis session
        3. AnalysisResponse is built from SessionData and returned

    See module docstring for the response body contract and the
    note on when to extract a dedicated pipeline orchestrator layer.

    PARAMETERS
    ----------
    file : UploadFile
        The uploaded image. FastAPI parses this from the multipart body.
        Required — FastAPI returns 422 automatically if absent.

    engine : TriggerEngine
        Injected by FastAPI via Depends(get_trigger_engine).

    session_manager : SessionManager
        Injected by FastAPI via Depends(get_session_manager).

    RETURNS
    -------
    AnalysisResponse
        Serialised to JSON by FastAPI. Always HTTP 200.
        Errors raise HTTPException instead of returning a response.

    ERROR RESPONSES
    ---------------
    HTTP 400 — validation failure (bad file, wrong type, too large)
    HTTP 500 — unexpected internal error (engine crash, OS error)

    Both error bodies follow the shape:
        { "detail": { "success": false, "error_code": "...", ... } }
    React reads: response.detail.error_code, response.detail.message
    """

    logger.info(f"Analyze endpoint: request received for '{file.filename}'")

    # ── STEP 1: Trigger Engine Validation ─────────────────────────
    try:
        validation_result = await engine.validate_upload(file)
        # validate_upload is async — it awaits file.read() internally.
        # Without await here we would receive a coroutine object,
        # not a ValidationResult. This is a common async mistake.

    except Exception as exc:
        # Unexpected error inside the Trigger Engine itself.
        # Distinct from a validation failure (which is handled below).
        # A validation failure is an expected outcome (valid=False).
        # An exception here means the engine crashed unexpectedly.
        logger.error(
            f"Analyze endpoint: Trigger Engine raised an exception — {exc}",
            exc_info=True
            # exc_info=True includes the full traceback in the log.
            # Essential for diagnosing unexpected crashes.
        )
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error_code="TRIGGER_ENGINE_ERROR",
                message="An unexpected error occurred during file validation. Please try again.",
                detail=str(exc)
            ).model_dump()
            # .model_dump() converts ErrorResponse to a plain dict.
            # HTTPException.detail accepts a dict — FastAPI sends it
            # as the value of the "detail" key in the JSON response:
            #   { "detail": { "success": false, "error_code": "...", ... } }
            # React reads: error.detail.error_code
        )

    # ── STEP 2: Handle Validation Failure ─────────────────────────
    if not validation_result.valid:
        # The Trigger Engine completed successfully but found the file
        # unacceptable. This is the expected failure path, not a crash.
        # Return 400 Bad Request — the client sent invalid input.
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
            # Same "detail" wrapper applies here:
            #   { "detail": { "success": false, "error_code": "FILE_TOO_LARGE", ... } }
            # React reads: error.detail.error_code, error.detail.message
        )

    # ── STEP 3: Session Creation ───────────────────────────────────
    # validation_result.valid is True here.
    # validation_result.privo_frame is guaranteed non-None when valid=True.
    # (See ValidationResult definition in trigger.py.)
    try:
        session = session_manager.create_session(validation_result.privo_frame)
        # Synchronous — no await needed.
        # SessionData is built in memory and stored in SessionManager._store.

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
                detail=str(exc)
            ).model_dump()
        )

    # ── STEP 4: Build the API Response ────────────────────────────
    # Explicit field-by-field mapping from SessionData → AnalysisResponse.
    #
    # WHY EXPLICIT AND NOT session.model_dump()?
    # -------------------------------------------
    # model_dump() would copy every SessionData field automatically.
    # But SessionData contains fields that must NOT appear in the API:
    #   - privo_frame.content → raw image bytes, not JSON-serialisable
    #   - internal timestamps in a format React doesn't need yet
    # Explicit mapping keeps the API contract intentional and visible.
    # If a new internal field is added to SessionData, it does not
    # accidentally leak into the API response.

    response = AnalysisResponse(
        success=True,

        session_id=session.session_id,
        # "PRIVO-SESSION-A3F8B21C"

        filename=session.privo_frame.filename,
        # "photo.jpg" for gallery, None for camera/video

        source=session.source,
        # InputSource.GALLERY → serialised as "gallery" (str Enum)

        status=session.status,
        # SessionStatus.PENDING → serialised as "pending" (str Enum)

        file_size_bytes=session.privo_frame.size_bytes,
        # Exact byte count computed from len(content) in PrivoFrame

        settings_loaded=session.settings_loaded,
        # True — set by SessionManager.create_session()

        message=_build_success_message(session.source, session.privo_frame.filename),

        settings=SettingsSnapshot(
            # Field-by-field mapping from DefaultSettings → SettingsSnapshot.
            # Intentionally explicit: if DefaultSettings gains an internal
            # field that should not be exposed, it won't appear here.
            theme=session.settings.theme,
            scanning_mode=session.settings.scanning_mode,
            metadata_retention=session.settings.metadata_retention,
            analysis_history=session.settings.analysis_history,
            cloud_processing=session.settings.cloud_processing
        )
    )

    logger.info(
        f"Analyze endpoint: response ready | "
        f"session={session.session_id} | "
        f"source={session.source.value} | "
        f"status={session.status.value}"
    )

    return response


# ─────────────────────────────────────────────────────────────────
# PRIVATE HELPERS
# ─────────────────────────────────────────────────────────────────

def _build_success_message(source: InputSource, filename) -> str:
    """
    Returns a source-aware success message for the frontend to display.

    WHY SOURCE-AWARE?
    -----------------
    "Image uploaded successfully" is misleading for a camera frame —
    nothing was "uploaded" in the traditional sense. The message should
    reflect what the user actually did.

    WHY A HELPER AND NOT INLINE?
    ----------------------------
    The if/elif block would add 10+ lines to the endpoint function,
    making the orchestration steps (validate → session → respond)
    harder to read. A named helper keeps the endpoint body clean.

    PARAMETERS
    ----------
    source : InputSource
        The input source type from the session (GALLERY, CAMERA, VIDEO).

    filename : Optional[str]
        The original filename. Only present for GALLERY source.

    RETURNS
    -------
    str — Human-readable message for the React frontend.

    WHY InputSource IS IMPORTED AT MODULE LEVEL, NOT LOCALLY
    ---------------------------------------------------------
    InputSource is imported at the top of this file alongside
    TriggerEngine. There is no circular import risk — trigger.py
    does not import anything from this endpoint file.

    A local import inside this function would duplicate the module-level
    import unnecessarily, which adds confusion: a reader would wonder
    why the import is done twice and what problem the local import
    was solving. It solves nothing here. Module-level import is correct.
    """
    if source == InputSource.GALLERY:
        display_name = filename if filename else "Image"
        return f"{display_name} received. Analysis pipeline ready."

    elif source == InputSource.CAMERA:
        return "Camera frame received. Analysis pipeline ready."

    elif source == InputSource.VIDEO:
        return "Video frame received. Analysis pipeline ready."

    else:
        # Fallback for any InputSource values added in the future.
        # Without this branch, a new InputSource member would silently
        # return None (Python functions return None implicitly).
        # This explicit fallback ensures a string is always returned.
        return "Input received. Analysis pipeline ready."
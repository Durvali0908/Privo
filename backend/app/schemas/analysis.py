"""
backend/app/schemas/analysis.py

PURPOSE
-------
This file defines the API response schemas for Privo's analysis endpoints.

A schema in this context means: the exact shape of the JSON data that
the FastAPI backend sends to the React frontend.

─────────────────────────────────────────────────────────────────────
WHY schemas/ IS SEPARATE FROM engine/
─────────────────────────────────────────────────────────────────────
The engine/ directory contains internal pipeline models:
    PrivoFrame      → holds raw bytes, not JSON-serialisable directly
    SessionData     → holds PrivoFrame, internal timestamps, full state
    ValidationResult→ internal trigger engine result

The schemas/ directory contains API boundary models:
    AnalysisResponse → only the fields the frontend needs, in clean JSON

WHY KEEP THEM SEPARATE?

Reason 1 — Internal models can contain non-JSON types.
    PrivoFrame.content is bytes (raw image data).
    You cannot send bytes in a JSON response.
    The schema selects only JSON-safe fields from the internal model.

Reason 2 — API contracts should be stable.
    Internal models change freely as the pipeline evolves.
    The API contract (what React expects) should change deliberately
    and intentionally. Separating schemas makes breaking changes visible.

Reason 3 — Single Responsibility Principle.
    engine/ models: "how does data move through the pipeline?"
    schemas/ models: "what does the frontend receive?"
    One question. One place. No mixing.

─────────────────────────────────────────────────────────────────────
WHAT THE FRONTEND RECEIVES IN WEEK 1
─────────────────────────────────────────────────────────────────────
{
    "success": true,
    "session_id": "PRIVO-SESSION-A3F8B21C",
    "filename": "photo.jpg",
    "source": "gallery",
    "status": "pending",
    "file_size_bytes": 2457600,
    "settings_loaded": true,
    "message": "Image uploaded successfully. Analysis pipeline ready.",
    "settings": {
        "theme": "system",
        "scanning_mode": "balanced",
        "metadata_retention": true,
        "analysis_history": true,
        "cloud_processing": false
    }
}

─────────────────────────────────────────────────────────────────────
HOW THIS FILE FITS IN THE ARCHITECTURE
─────────────────────────────────────────────────────────────────────
Called by:
    app/api/v1/endpoints/analyze.py
        → imports AnalysisResponse and ErrorResponse
        → builds an AnalysisResponse from SessionData fields
        → returns it as the endpoint's response body
        → FastAPI serialises it to JSON automatically

Reads from:
    app/engine/session.py
        → SessionData fields are mapped into AnalysisResponse fields
        → DefaultSettings is mapped into SettingsSnapshot

Consumed by:
    React frontend (src/types/analysis.ts)
        → TypeScript interface mirrors AnalysisResponse exactly

FUTURE SCHEMAS TO ADD IN THIS FILE
------------------------------------
As Privo grows, new response schemas will be added here:
    DetectionResponse    → Week 3: detected regions and signals
    RiskScoreResponse    → Week 4: exposure scores per category
    HeatmapResponse      → Week 5: heatmap coordinates and overlays
    ProtectionResponse   → Week 6: applied protections and export path
    SessionStatusResponse→ Future: current status of an ongoing session

All of them follow the same pattern as AnalysisResponse below.
"""

from pydantic import BaseModel, Field
# BaseModel: Foundation for all Privo data models.
#   Provides automatic JSON serialisation, type validation, and
#   the .model_dump() method to convert to a dictionary.
# Field: Adds metadata (default values, descriptions) to model fields.
#   FastAPI uses Field descriptions to generate API documentation
#   automatically at /docs (Swagger UI).

from typing import Optional
# Optional[X]: The value is either X or None.
# Used for fields that are not always present.
# Example: filename is None for camera frames (they have no filename).

from app.pipeline.intake.session import SessionStatus
# SessionStatus: The enum of valid session lifecycle stages.
# Imported here so AnalysisResponse can include the current status
# using the same type as SessionData — no string duplication.

from app.pipeline.intake.trigger import InputSource
# InputSource: The enum of valid input sources (GALLERY, CAMERA, VIDEO).
# Imported here so AnalysisResponse can report the source type
# in the same format as the internal pipeline uses.


# ─────────────────────────────────────────────────────────────────
# SETTINGS SNAPSHOT
# A clean, JSON-safe copy of the session settings.
# Mirrors DefaultSettings from session.py but lives in schemas/
# because its purpose is API communication, not internal state.
# ─────────────────────────────────────────────────────────────────

class SettingsSnapshot(BaseModel):
    """
    A read-only snapshot of the session settings sent to the frontend.

    WHY NOT REUSE DefaultSettings FROM session.py?
    -----------------------------------------------
    DefaultSettings in session.py is an internal engine model.
    SettingsSnapshot is a public API schema.

    In Week 1 they are identical in structure. In the future they may
    diverge:
    - DefaultSettings may gain internal fields the frontend shouldn't see
    - SettingsSnapshot may gain computed or derived fields for display
    - DefaultSettings may change as the pipeline evolves; SettingsSnapshot
      should only change when the API contract intentionally changes

    Keeping them separate maintains that boundary cleanly.

    FIELDS
    ------
    All fields mirror DefaultSettings but are described from the
    frontend's perspective — what will the React app do with each value?

    theme : str
        Used by the frontend to set dark/light/system mode.
        Backend engines do not read this field.

    scanning_mode : str
        Displayed in the UI as the current analysis intensity.
        Read by the Risk Scoring Engine to determine check depth.

    metadata_retention : bool
        Displayed as a toggle in the settings UI (future).
        Read by the Metadata Extractor to decide what to include.

    analysis_history : bool
        Displayed as a toggle in the settings UI (future).
        Read by the Memory Engine to decide whether to persist.

    cloud_processing : bool
        Displayed as a toggle in the settings UI (future).
        Read by the Detection Engine to decide processing location.
    """

    theme: str = Field(
        description="UI theme: 'light', 'dark', or 'system'"
    )

    scanning_mode: str = Field(
        description="Analysis intensity: 'fast', 'balanced', or 'thorough'"
    )

    metadata_retention: bool = Field(
        description="Whether metadata is included in analysis results"
    )

    analysis_history: bool = Field(
        description="Whether this session is stored in analysis history"
    )

    cloud_processing: bool = Field(
        description="Whether cloud AI processing is enabled"
    )


# ─────────────────────────────────────────────────────────────────
# ANALYSIS RESPONSE
# The main response body for the POST /api/v1/analyze endpoint.
# This is what React receives and displays after uploading an image.
# ─────────────────────────────────────────────────────────────────

class AnalysisResponse(BaseModel):
    """
    The complete JSON response for a successful image upload.

    This is the public API contract between the FastAPI backend
    and the React frontend for the analysis endpoint.

    HOW FastAPI USES THIS
    ----------------------
    The analyze.py endpoint declares this as its response model:

        @router.post("/analyze", response_model=AnalysisResponse)
        async def analyze(file: UploadFile):
            ...
            return AnalysisResponse(...)

    FastAPI then:
    1. Validates the returned object matches AnalysisResponse
    2. Serialises it to JSON automatically
    3. Sets Content-Type: application/json on the response
    4. Generates Swagger documentation from the field descriptions

    HOW REACT USES THIS
    --------------------
    The TypeScript interface in src/types/analysis.ts mirrors this
    schema exactly. When React receives the JSON, TypeScript ensures
    the component code accesses only fields that actually exist.

    WEEK 1 RESPONSE EXAMPLE
    ------------------------
    {
        "success": true,
        "session_id": "PRIVO-SESSION-A3F8B21C",
        "filename": "photo.jpg",
        "source": "gallery",
        "status": "pending",
        "file_size_bytes": 2457600,
        "settings_loaded": true,
        "message": "Image uploaded successfully. Analysis pipeline ready.",
        "settings": {
            "theme": "system",
            "scanning_mode": "balanced",
            "metadata_retention": true,
            "analysis_history": true,
            "cloud_processing": false
        }
    }

    FUTURE FIELDS TO ADD
    ---------------------
    When detection results are ready (Week 3), this response will gain:
        "detections": [...] or a separate DetectionResponse schema

    When risk scoring is ready (Week 4), this response will gain:
        "risk_score": 72,
        "exposure_categories": [...]

    The structure will grow incrementally. The frontend always checks
    whether optional fields are present before rendering them.

    FIELDS
    ------
    success : bool
        Always True for AnalysisResponse.
        (False responses use ErrorResponse instead.)
        The frontend checks this first before reading other fields.

    session_id : str
        The unique session identifier.
        React stores this and sends it in future requests:
            GET /api/v1/session/{session_id}/status
            POST /api/v1/session/{session_id}/protect
        This is how the frontend tracks which analysis it's viewing.

    filename : Optional[str]
        The original filename from the upload.
        None for camera and video frames (they have no filename).
        Displayed in the UI as: "Analysing: photo.jpg"

    source : InputSource
        Which input type produced this session.
        Serialised as a string: "gallery", "camera", or "video".
        Used by the frontend to decide which UI elements to show.
        Example: camera source → show "Retake" button instead of
        "Upload Different Image".

    status : SessionStatus
        Current pipeline status. Serialised as: "pending"
        In Week 1: always "pending" (no processing happens yet).
        Future: frontend polls this to show progress indicators.

    file_size_bytes : Optional[int]
        File size in bytes.
        Displayed in the UI as a human-readable size:
            "2.4 MB" (frontend does this conversion in TypeScript)
        None if size could not be determined.

    settings_loaded : bool
        Confirms that default settings were applied to this session.
        In Week 1: the frontend displays this as a pipeline status check.
        Future: if False, the frontend shows a settings warning.

    message : str
        A human-readable status message for the frontend to display.
        Examples:
            "Image uploaded successfully. Analysis pipeline ready."
            "Camera frame received. Analysis pipeline ready."

    settings : SettingsSnapshot
        The settings applied to this session.
        The frontend uses this to display the current configuration
        in the settings panel (future Settings UI).
    """

    success: bool = Field(
        description="True for successful responses"
    )

    session_id: str = Field(
        description="Unique session identifier, e.g. PRIVO-SESSION-A3F8B21C"
    )

    filename: Optional[str] = Field(
        default=None,
        description="Original filename, None for camera/video sources"
    )

    source: InputSource = Field(
        description="Input source type: 'gallery', 'camera', or 'video'"
    )

    status: SessionStatus = Field(
        description="Current session lifecycle status"
    )

    file_size_bytes: Optional[int] = Field(
        default=None,
        description="File size in bytes, None if unavailable"
    )

    settings_loaded: bool = Field(
        description="Confirms default settings were loaded for this session"
    )

    message: str = Field(
        description="Human-readable status message for the frontend"
    )

    settings: SettingsSnapshot = Field(
        description="Settings applied to this analysis session"
    )


# ─────────────────────────────────────────────────────────────────
# ERROR RESPONSE
# The response body for failed requests.
# Used when validation fails or an unexpected error occurs.
# ─────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """
    The JSON response body for failed requests.

    WHY A SEPARATE ERROR SCHEMA?
    -----------------------------
    FastAPI raises HTTPException for errors, which produces a default
    JSON body like: {"detail": "File too large"}

    ErrorResponse gives us a richer, structured error format that:
    - Includes a machine-readable error_code for the frontend to act on
    - Includes a human-readable message to display to the user
    - Is consistent with AnalysisResponse in having a "success" field
    - Can be extended with additional context fields in the future

    HOW THE FRONTEND USES error_code
    ----------------------------------
    The React frontend can switch on error_code to show specific UI:

    if (error.error_code === "FILE_TOO_LARGE") {
        showMessage("Try compressing your image before uploading.")
    } else if (error.error_code === "UNSUPPORTED_EXTENSION") {
        showMessage("Only JPG, PNG, WebP, and HEIC files are supported.")
    }

    Without error_code, the frontend can only show a generic message.

    ERROR RESPONSE EXAMPLE
    ----------------------
    {
        "success": false,
        "error_code": "FILE_TOO_LARGE",
        "message": "File is 45.2 MB. Maximum allowed size is 20 MB.",
        "detail": null
    }

    FIELDS
    ------
    success : bool
        Always False for ErrorResponse.

    error_code : str
        Machine-readable error identifier.
        Matches the error_code values from ValidationResult in trigger.py:
            "MISSING_FILE"
            "MISSING_EXTENSION"
            "UNSUPPORTED_EXTENSION"
            "FILE_TOO_LARGE"
            "MISSING_CONTENT"
        Future engine errors will add new codes here.

    message : str
        Human-readable explanation to display to the user.
        Same value as ValidationResult.error_message from trigger.py.

    detail : Optional[str]
        Optional additional context.
        Used for unexpected server errors where a stack trace summary
        or additional diagnostic information may be helpful.
        None for validation errors (message is sufficient).
        Future: In production, this field is suppressed to avoid
        leaking internal implementation details to users.
    """

    success: bool = Field(
        default=False,
        description="Always False for error responses"
    )

    error_code: str = Field(
        description="Machine-readable error code"
    )

    message: str = Field(
        description="Human-readable error message for display"
    )

    detail: Optional[str] = Field(
        default=None,
        description="Optional additional diagnostic context"
    )
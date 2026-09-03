"""
backend/app/engine/trigger.py

PURPOSE
-------
The Trigger Engine is Privo's entry-point gatekeeper.

Every image — whether from a gallery upload, a camera capture,
or a future video stream — must pass through this engine first.

It performs three validation checks and returns a structured result.
If validation fails at any step, the pipeline stops immediately.
No other engine ever receives input that has not been validated here.

─────────────────────────────────────────────────────────────────────
THE CORE ARCHITECTURAL DECISION IN THIS FILE
─────────────────────────────────────────────────────────────────────
The Trigger Engine does NOT accept FastAPI's UploadFile directly as
its internal type. Instead, it normalises every input source into a
single shared container called PrivoFrame.

WHY?

FastAPI's UploadFile is specific to HTTP file uploads. A camera frame
is raw bytes from a WebRTC or MediaStream. A video frame is a NumPy
array from OpenCV. If the Trigger Engine accepted UploadFile internally,
the entire pipeline would be permanently coupled to HTTP uploads — and
rewriting it for Phase 2 (live camera) or Phase 3 (video) would require
touching every engine in the stack.

With PrivoFrame:
- The Detection Engine sees PrivoFrame. Always.
- The Session Manager sees PrivoFrame. Always.
- The source (gallery / camera / video) is just metadata on PrivoFrame.
- Adding a new source means writing one new adapter method. Nothing else changes.

─────────────────────────────────────────────────────────────────────
THREE-PHASE INPUT STRATEGY
─────────────────────────────────────────────────────────────────────

Phase 1 — Gallery (NOW):
    User selects image file → React sends multipart/form-data →
    FastAPI receives UploadFile → validate_upload() converts to PrivoFrame →
    pipeline runs

Phase 2 — Camera capture (FUTURE):
    User opens camera in React PWA → captures a frame →
    React sends raw bytes → validate_frame() converts to PrivoFrame →
    same pipeline runs

Phase 3 — Live video / continuous analysis (FUTURE):
    Camera stream active → frames extracted at N fps →
    each frame → validate_frame() → Detection Engine only
    (no new session per frame — session persists for stream duration)

In all three phases:
    PrivoFrame → Trigger Engine → Detection Engine
    The Detection Engine never changes. Only the source adapter changes.

─────────────────────────────────────────────────────────────────────
VALIDATION CHECKS (in order, short-circuit on failure)
─────────────────────────────────────────────────────────────────────
1. Presence Check   — does the frame have content?
2. Extension Check  — is the format in the allowed list? (gallery only)
3. Size Check       — is the content under the maximum allowed size?

HOW THIS FILE COMMUNICATES WITH OTHER MODULES
----------------------------------------------
Called by:
    app/api/v1/endpoints/analyze.py
        → passes UploadFile from React
        → receives ValidationResult

Produces:
    PrivoFrame (normalised input for the rest of the pipeline)
    ValidationResult (validation outcome for the endpoint)

Reads from:
    app/core/config.py
        → settings.allowed_extensions
        → settings.max_file_size_bytes

Logs via:
    app/core/logging.py
        → records every validation step and outcome

FUTURE MODULES THAT WILL DEPEND ON THIS FILE
---------------------------------------------
- session.py              → receives PrivoFrame after validation
- detection_engine        → receives PrivoFrame (Week 3)
- metadata_extractor      → reads PrivoFrame.filename and .source
- roi_manager             → reads PrivoFrame.content (raw bytes)
- camera_adapter (future) → calls validate_frame() with raw bytes
- video_adapter (future)  → calls validate_frame() per video frame
"""

import os
# os: Python's operating system interface.
# Used for os.path.splitext() to extract file extensions.
# Example: os.path.splitext("photo.jpg") → ("photo", ".jpg")

from enum import Enum
# Enum: Python's enumeration base class.
# An Enum defines a fixed set of named values.
# We use it to declare all valid input sources for Privo.
# Why Enum instead of plain strings?
#   - "gallery" can be mistyped as "Gallery" or "GALLERY" — no error.
#   - InputSource.GALLERY cannot be mistyped — Python raises AttributeError.
#   - IDEs autocomplete Enum values. They don't autocomplete strings.
#   - Adding a new source means adding one line to InputSource.
#     Every place in the codebase that checks the source type
#     benefits immediately without hunting for string literals.

from typing import Optional
# Optional[X] means the value can be X or None.
# Used for fields that may not be present for every input source.
# Example: filename is meaningful for gallery uploads but not camera frames.

from pydantic import BaseModel, Field
# BaseModel: Foundation for all Privo data models.
# Provides type validation, serialisation, and IDE autocomplete.
# Field: Adds metadata (default values, descriptions) to model fields.

from fastapi import UploadFile
# UploadFile: FastAPI's class representing a file uploaded via HTTP.
# We receive this from the React frontend in Phase 1.
# We convert it to PrivoFrame immediately — it does not travel
# further into the pipeline in its original form.

from app.core.config import settings
# settings: Central configuration singleton from config.py.
# We read:
#   settings.allowed_extensions  — list of valid extensions
#   settings.max_file_size_bytes — computed from settings.max_file_size_mb

from app.core.logging import get_logger
# get_logger: Logging factory from logging.py.
# Returns a Logger namespaced under "privo.app.engine.trigger".

logger = get_logger(__name__)
# __name__ = "app.engine.trigger"
# Logger name = "privo.app.engine.trigger"


# ─────────────────────────────────────────────────────────────────
# INPUT SOURCE ENUM
# Declares every valid input source Privo supports or will support.
# The pipeline uses this to make source-aware decisions where needed.
# ─────────────────────────────────────────────────────────────────

class InputSource(str, Enum):
    """
    Declares the known input sources for Privo's pipeline.

    WHY INHERIT FROM BOTH str AND Enum?
    ------------------------------------
    Inheriting from str makes each enum member behave like a string.
    This means InputSource.GALLERY == "gallery" is True.
    It also means Pydantic can serialise it directly to JSON as a string:
        {"source": "gallery"}  not  {"source": "InputSource.GALLERY"}
    This is important because PrivoFrame will be serialised to JSON
    when the API response is built.

    CURRENT MEMBERS
    ---------------
    GALLERY : Images selected from the device's photo library.
              Arrive as UploadFile via multipart/form-data.
              Have filenames and may have EXIF metadata.

    CAMERA  : Single photo captured from the device camera.
              Arrive as raw bytes via a future /capture endpoint.
              May not have a filename. May have GPS from capture context.

    VIDEO   : Individual frames extracted from a video stream.
              Arrive as raw bytes from a future video analysis pipeline.
              No filename. Frame index and timestamp are relevant instead.

    ADDING A NEW SOURCE IN THE FUTURE
    ----------------------------------
    If Privo gains a screenshot analysis feature, add:
        SCREENSHOT = "screenshot"
    That's the only change needed in this file.
    The pipeline picks it up automatically via PrivoFrame.source.
    """

    GALLERY = "gallery"
    CAMERA  = "camera"
    VIDEO   = "video"


# ─────────────────────────────────────────────────────────────────
# PRIVO FRAME — THE NORMALISED INPUT CONTAINER
# This is the single type that flows through the entire pipeline.
# Every input source is converted into a PrivoFrame before
# entering validation. Everything downstream sees only PrivoFrame.
# ─────────────────────────────────────────────────────────────────

class PrivoFrame(BaseModel):
    """
    The normalised, source-agnostic input container for Privo's pipeline.

    WHAT IS A PrivoFrame?
    ----------------------
    Regardless of where an image comes from — a gallery upload,
    a camera capture, or a video stream — by the time it enters
    the Trigger Engine's validation logic, it is a PrivoFrame.

    Think of PrivoFrame as the "common language" all input sources
    are translated into before the pipeline begins processing.

    WHY NOT USE UploadFile DIRECTLY?
    ---------------------------------
    UploadFile is a FastAPI HTTP concept. It only exists in the context
    of an HTTP multipart/form-data request. Camera frames and video
    frames are not HTTP uploads — they arrive as raw bytes. If the
    pipeline depended on UploadFile, it would break the moment we
    added a camera input.

    PrivoFrame abstracts away the source. The Detection Engine doesn't
    care if the bytes came from a file picker or a camera — it just
    processes the bytes.

    FIELDS
    ------
    content : bytes
        The raw image data. This is what OpenCV, MediaPipe, YOLO,
        and EasyOCR will all read in the future.
        For gallery images: the full file bytes.
        For camera frames: the JPEG-encoded frame bytes from the browser.
        For video frames: the bytes of one decoded frame.

    source : InputSource
        Which input type produced this frame.
        Used by:
          - Trigger Engine: to decide which checks apply
            (extension check only applies to gallery uploads)
          - Session Manager: to tag the session with its origin
          - Analytics Dashboard (future): to report usage by source type
          - Metadata Extractor (future): gallery images have EXIF,
            camera frames have GPS from the capture context instead

    filename : Optional[str]
        Original filename from the upload. Only meaningful for GALLERY.
        None for CAMERA and VIDEO (frames don't have filenames).
        Stored in session data for display and audit logging.

    extension : Optional[str]
        Lowercased extension without dot, e.g. "jpg", "png", "heic".
        Extracted from filename for GALLERY inputs.
        None for CAMERA and VIDEO.
        Future use: Metadata Extractor uses this to select the right
        ExifTool parser for the image format.

    frame_index : Optional[int]
        For VIDEO source only.
        The sequential number of this frame in the video stream.
        Used by the future Video Adapter to track analysis progress
        and by the Analytics Dashboard to report frame-level timing.

    size_bytes : Optional[int]
        The size of the content in bytes.
        Computed from len(content) during PrivoFrame construction,
        or passed in directly when size is known from the source.
        Used by the size validation check and stored in session data.
    """

    model_config = {"arbitrary_types_allowed": True}
    # arbitrary_types_allowed: Pydantic normally only accepts types it
    # knows how to validate (str, int, bool, etc.).
    # bytes is supported natively, but this config flag is set
    # explicitly as documentation: PrivoFrame holds raw binary data.

    content: bytes = Field(description="Raw image bytes")

    source: InputSource = Field(description="Which input source produced this frame")

    filename: Optional[str] = Field(
        default=None,
        description="Original filename, only present for GALLERY source"
    )

    extension: Optional[str] = Field(
        default=None,
        description="Lowercased extension without dot, e.g. 'jpg'"
    )

    frame_index: Optional[int] = Field(
        default=None,
        description="Frame number in a video stream, only for VIDEO source"
    )

    size_bytes: Optional[int] = Field(
        default=None,
        description="Size of content in bytes"
    )


# ─────────────────────────────────────────────────────────────────
# VALIDATION RESULT — STRUCTURED OUTPUT OF TRIGGER ENGINE
# ─────────────────────────────────────────────────────────────────

class ValidationResult(BaseModel):
    """
    The structured result returned by every TriggerEngine validation method.

    WHY A PYDANTIC MODEL?
    ----------------------
    A plain dict like {"valid": True} has no type guarantee.
    ValidationResult guarantees:
    - result.valid is always bool
    - result.privo_frame is always PrivoFrame or None
    - result.error_code is always str or None
    The API endpoint, Session Manager, and future engines can all rely
    on this contract without defensive checks like:
        if "valid" in result and result["valid"] == True: ...

    HOW THIS TRAVELS THROUGH THE PIPELINE
    ---------------------------------------
    analyze.py:
        result = engine.validate_upload(file)
        if not result.valid:
            raise HTTPException(400, result.error_message)
        # Pass result.privo_frame to Session Manager:
        session = session_manager.create_session(result.privo_frame)

    FIELDS
    ------
    valid : bool
        True if all applicable checks passed. False otherwise.

    privo_frame : Optional[PrivoFrame]
        The normalised input container, populated only when valid=True.
        This is what flows downstream to the Session Manager and engines.
        None when valid=False (no point passing invalid data forward).

    error_code : Optional[str]
        Machine-readable failure code. None when valid=True.
        Examples: "MISSING_FILE", "UNSUPPORTED_EXTENSION", "FILE_TOO_LARGE"
        Used by the endpoint to categorise failures for logging/analytics.

    error_message : Optional[str]
        Human-readable failure explanation. None when valid=True.
        This is shown to the user in the React frontend.
    """

    valid: bool = Field(description="True if all validation checks passed")

    privo_frame: Optional[PrivoFrame] = Field(
        default=None,
        description="Normalised input container, populated only when valid=True"
    )

    error_code: Optional[str] = Field(
        default=None,
        description="Machine-readable error code, None when valid"
    )

    error_message: Optional[str] = Field(
        default=None,
        description="Human-readable error message, None when valid"
    )


# ─────────────────────────────────────────────────────────────────
# TRIGGER ENGINE
# ─────────────────────────────────────────────────────────────────

class TriggerEngine:
    """
    The Trigger Engine — Privo's entry-point gatekeeper.

    Provides source-specific entry points (validate_upload, validate_frame)
    that each convert their input into a PrivoFrame, then delegate to the
    shared internal validation logic.

    PUBLIC INTERFACE
    ----------------
    validate_upload(file: UploadFile) → ValidationResult
        Entry point for Phase 1 (gallery / file picker).
        Converts UploadFile → PrivoFrame → validates.

    validate_frame(content: bytes, source: InputSource, ...) → ValidationResult
        Entry point for Phase 2 and 3 (camera / video).
        Wraps raw bytes → PrivoFrame → validates.

    INTERNAL LOGIC
    --------------
    _validate_privo_frame(frame: PrivoFrame) → ValidationResult
        The shared validation core. Both public methods call this.
        Runs: presence check → extension check (gallery only) → size check.

    WHY TWO PUBLIC METHODS?
    -----------------------
    validate_upload and validate_frame have different inputs but the same
    validation logic. Separating them at the public interface keeps the
    caller's code clean (no source-specific branching in the endpoint),
    while sharing the validation core avoids duplication.

    In Phase 2, the camera endpoint will call:
        engine.validate_frame(frame_bytes, InputSource.CAMERA)
    It never touches validate_upload. The endpoint code is clean.
    """

    # ── PUBLIC ENTRY POINT: GALLERY / FILE UPLOAD ─────────────────

    async def validate_upload(self, file: UploadFile) -> ValidationResult:
        """
        Entry point for Phase 1: gallery image uploads.

        Reads the UploadFile, converts it to a PrivoFrame, then
        delegates to the shared validation logic.

        WHY async?
        ----------
        FastAPI's UploadFile.read() is a coroutine — it must be awaited.
        The bytes are read from the HTTP request body asynchronously.
        This is why the method is async: it must await file.read().

        All other validation methods are synchronous because they
        work with data that is already in memory (bytes, not streams).

        PARAMETERS
        ----------
        file : UploadFile
            The file object provided by FastAPI from the HTTP request.

        RETURNS
        -------
        ValidationResult with privo_frame populated if valid=True.
        """
        logger.info(f"Trigger Engine: validating gallery upload — '{file.filename}'")

        # Read the full file content into memory as bytes.
        # await is required because this reads from the HTTP request stream.
        content: bytes = await file.read()
        # content is now a bytes object holding the raw image data.
        # bytes is Python's type for raw binary data.
        # b"\xff\xd8\xff" would be the start of a JPEG, for example.

        # Seek back to the beginning of the file after reading.
        # FastAPI's UploadFile is backed by a SpooledTemporaryFile.
        # After read(), the cursor is at the end of the file.
        # Some future modules may need to read the file again.
        # Seeking to 0 resets the cursor so it can be read again.
        await file.seek(0)

        # Extract the extension from the filename before building PrivoFrame
        extension = self._extract_extension(file.filename)

        # Build the normalised PrivoFrame from the upload data
        frame = PrivoFrame(
            content=content,
            source=InputSource.GALLERY,
            filename=file.filename,
            extension=extension,
            size_bytes=len(content)
            # len(content) gives the exact byte count from what we read.
            # This is more reliable than file.size, which comes from the
            # HTTP Content-Length header and may be None if the client
            # did not send that header.
        )

        return self._validate_privo_frame(frame)

    # ── PUBLIC ENTRY POINT: CAMERA / VIDEO FRAMES (FUTURE) ────────

    def validate_frame(
        self,
        content: bytes,
        source: InputSource,
        frame_index: Optional[int] = None
    ) -> ValidationResult:
        """
        Entry point for Phase 2 and 3: camera captures and video frames.

        Accepts raw bytes and wraps them into a PrivoFrame before
        delegating to the shared validation logic.

        This method is synchronous (not async) because by the time
        camera bytes arrive here, they are already in memory — there
        is no stream to await.

        PARAMETERS
        ----------
        content : bytes
            Raw image bytes. For camera: JPEG-encoded frame from browser.
            For video: decoded frame bytes from OpenCV or FFmpeg.

        source : InputSource
            Must be InputSource.CAMERA or InputSource.VIDEO.
            Determines which validation checks apply.

        frame_index : Optional[int]
            For VIDEO source: the frame number in the stream.
            None for CAMERA source.

        RETURNS
        -------
        ValidationResult with privo_frame populated if valid=True.

        FUTURE USAGE (Phase 2 camera endpoint):
        ----------------------------------------
        @router.post("/capture")
        async def capture_endpoint(frame_data: bytes = Body(...)):
            engine = TriggerEngine()
            result = engine.validate_frame(frame_data, InputSource.CAMERA)
            if not result.valid:
                raise HTTPException(400, result.error_message)
            session = session_manager.create_session(result.privo_frame)
            ...
        """
        logger.info(
            f"Trigger Engine: validating {source.value} frame"
            + (f" #{frame_index}" if frame_index is not None else "")
        )

        frame = PrivoFrame(
            content=content,
            source=source,
            filename=None,
            # Camera and video frames have no filename.
            # The Metadata Extractor will look at GPS context instead.
            extension=None,
            # No extension for raw frame bytes.
            frame_index=frame_index,
            size_bytes=len(content)
        )

        return self._validate_privo_frame(frame)

    # ── SHARED INTERNAL VALIDATION CORE ───────────────────────────

    def _validate_privo_frame(self, frame: PrivoFrame) -> ValidationResult:
        """
        The shared validation core. Called by both public methods.

        Runs three ordered checks. Fails fast on the first failure.
        Extension check is skipped for non-gallery sources (camera and
        video frames have no extension to check).

        PARAMETERS
        ----------
        frame : PrivoFrame
            The already-constructed normalised input container.

        RETURNS
        -------
        ValidationResult
            valid=True  → privo_frame is populated, pipeline continues
            valid=False → error_code and error_message describe the failure
        """

        # ── CHECK 1: Content Presence ──────────────────────────────
        presence_result = self._check_content_presence(frame)
        if not presence_result.valid:
            return presence_result

        # ── CHECK 2: Extension (Gallery only) ─────────────────────
        # Camera and video frames have no extension to validate.
        # Applying this check to them would cause false rejections.
        if frame.source == InputSource.GALLERY:
            extension_result = self._check_extension(frame)
            if not extension_result.valid:
                return extension_result

        # ── CHECK 3: Size ──────────────────────────────────────────
        size_result = self._check_size(frame)
        if not size_result.valid:
            return size_result

        # ── ALL CHECKS PASSED ──────────────────────────────────────
        logger.info(
            f"Trigger Engine: validation passed | "
            f"source={frame.source.value} | "
            f"file='{frame.filename}' | "
            f"ext='{frame.extension}' | "
            f"size={frame.size_bytes} bytes"
        )

        return ValidationResult(valid=True, privo_frame=frame)

    # ── PRIVATE VALIDATION CHECKS ─────────────────────────────────

    def _check_content_presence(self, frame: PrivoFrame) -> ValidationResult:
        """
        CHECK 1: Content Presence

        Verifies the frame actually contains bytes.
        Catches: empty uploads, failed camera captures, corrupted frames.

        For gallery: catches the case where the HTTP body was empty.
        For camera: catches the case where the browser sent no data.
        For video: catches the case where frame extraction failed.
        """
        if not frame.content or len(frame.content) == 0:
            logger.warning(
                f"Trigger Engine: presence check failed — "
                f"no content in {frame.source.value} frame"
            )
            return ValidationResult(
                valid=False,
                error_code="MISSING_CONTENT",
                error_message="No image data was received. Please try again."
            )

        logger.debug(
            f"Trigger Engine: presence check passed — "
            f"{len(frame.content)} bytes received"
        )
        return ValidationResult(valid=True, privo_frame=frame)

    def _check_extension(self, frame: PrivoFrame) -> ValidationResult:
        """
        CHECK 2: Extension Validation (Gallery source only)

        Verifies the file extension is in Privo's allowed list.

        WHY ONLY FOR GALLERY?
        ----------------------
        Gallery images have filenames and therefore extensions.
        Camera and video frames are raw bytes — they have no filename
        and no extension to check. They enter the pipeline as bytes
        directly without a file container around them.

        IMPORTANT LIMITATION (Week 1)
        ------------------------------
        This checks the extension string only, not the actual binary
        signature (magic bytes) inside the file. A renamed .exe would
        pass this check. The Security Hardening Module (future) will
        add magic byte verification using the `python-magic` library.
        For Week 1, extension checking is the appropriate first filter.
        """
        if not frame.extension:
            logger.warning(
                f"Trigger Engine: extension check failed — "
                f"no extension found in '{frame.filename}'"
            )
            return ValidationResult(
                valid=False,
                error_code="MISSING_EXTENSION",
                error_message="The file has no extension. Please upload a valid image file."
            )

        if frame.extension not in settings.allowed_extensions:
            allowed = ", ".join(settings.allowed_extensions)
            logger.warning(
                f"Trigger Engine: extension check failed — "
                f"'.{frame.extension}' not in allowed list"
            )
            return ValidationResult(
                valid=False,
                error_code="UNSUPPORTED_EXTENSION",
                error_message=(
                    f"'.{frame.extension}' is not a supported format. "
                    f"Privo accepts: {allowed}."
                )
            )

        logger.debug(
            f"Trigger Engine: extension check passed — '.{frame.extension}'"
        )
        return ValidationResult(valid=True, privo_frame=frame)

    def _check_size(self, frame: PrivoFrame) -> ValidationResult:
        """
        CHECK 3: Size Validation

        Verifies the content does not exceed the maximum allowed size.

        For gallery: size comes from len(file bytes read).
        For camera: size comes from len(frame bytes received).
        For video: size comes from len(frame bytes from decoder).

        Unlike the previous version of this check, we always have
        size_bytes here because we compute it from len(content)
        during PrivoFrame construction — we no longer depend on
        the HTTP Content-Length header, which could be None.
        """
        if frame.size_bytes is None:
            # Defensive fallback — should not occur since we set
            # size_bytes=len(content) in both public entry points.
            logger.debug("Trigger Engine: size check skipped — size_bytes is None")
            return ValidationResult(valid=True, privo_frame=frame)

        if frame.size_bytes > settings.max_file_size_bytes:
            size_mb = frame.size_bytes / (1024 * 1024)
            limit_mb = settings.max_file_size_mb
            logger.warning(
                f"Trigger Engine: size check failed — "
                f"{size_mb:.1f} MB exceeds {limit_mb} MB limit"
            )
            return ValidationResult(
                valid=False,
                error_code="FILE_TOO_LARGE",
                error_message=(
                    f"File is {size_mb:.1f} MB. "
                    f"Maximum allowed size is {limit_mb} MB."
                )
            )

        size_mb = frame.size_bytes / (1024 * 1024)
        logger.debug(
            f"Trigger Engine: size check passed — "
            f"{frame.size_bytes} bytes ({size_mb:.2f} MB)"
        )
        return ValidationResult(valid=True, privo_frame=frame)

    # ── PRIVATE HELPERS ───────────────────────────────────────────

    def _extract_extension(self, filename: Optional[str]) -> Optional[str]:
        """
        Extracts and normalises the file extension from a filename.

        RETURNS
        -------
        str  → lowercased extension without leading dot: "jpg", "png"
        None → if filename is None, empty, or has no extension

        EXAMPLES
        --------
        "photo.JPG"   → "jpg"
        "image.jpeg"  → "jpeg"
        "file"        → None
        None          → None
        ".hidden"     → None  (no actual extension)

        WHY os.path.splitext?
        ----------------------
        os.path.splitext is the standard, cross-platform way to split a
        filename into base and extension. It handles edge cases like
        dotfiles (.hidden) and multiple dots (archive.tar.gz) correctly.
        """
        if not filename:
            return None

        _, ext = os.path.splitext(filename)
        # _ : the base name ("photo") — we don't need it here
        # ext: the extension (".jpg") — this is what we want

        if not ext:
            return None

        return ext.lstrip(".").lower()
        # lstrip("."): removes the leading dot → "jpg"
        # lower():     normalises case       → "JPG" becomes "jpg"
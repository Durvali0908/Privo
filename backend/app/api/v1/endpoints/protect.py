"""
app/api/v1/endpoints/protect.py

POST /api/v1/session/{session_id}/protect

Re-detects regions on the session's stored image, applies the requested
protections, and returns the protected image bytes.

Fails closed: if a requested protection cannot run (detector or OCR
unavailable), an error is returned instead of an unprotected image.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from app.core.logging import get_logger
from app.pipeline.intake.session import SessionManager
from app.pipeline.detection.detection_engine import DetectionEngine
from app.pipeline.classification.signal_classification import (
    ClassificationResult,
    SignalClassificationEngine,
)
from app.pipeline.export.final_image_builder import FinalImageBuilder, ProtectionRequest
from app.schemas.analysis import ErrorResponse

logger = get_logger(__name__)
router = APIRouter()


def get_session_manager() -> SessionManager:
    return SessionManager()


def _fail(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail=ErrorResponse(error_code=code, message=message).model_dump(),
    )


def _ocr_available() -> bool:
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


@router.post(
    "/session/{session_id}/protect",
    summary="Apply protections and return the protected image",
    tags=["Protection"],
)
async def protect(
    session_id: str,
    body: ProtectionRequest,
    request: Request,
    session_mgr: SessionManager = Depends(get_session_manager),
) -> Response:
    session = session_mgr.get_session(session_id)
    if session is None:
        raise _fail(404, "SESSION_NOT_FOUND",
                    "Session not found or has expired. Please analyse the image again.")

    frame = session.privo_frame
    if not frame.content:
        raise _fail(422, "NO_IMAGE_DATA", "Session image data is unavailable.")

    face_mesh = getattr(request.app.state, "face_mesh", None)
    if body.protect_faces and face_mesh is None:
        raise _fail(503, "FACE_DETECTOR_UNAVAILABLE",
                    "Face protection is unavailable because the face detector is not loaded.")

    needs_text = body.protect_documents or body.protect_text
    if needs_text and not _ocr_available():
        raise _fail(503, "OCR_UNAVAILABLE",
                    "Text and document protection are unavailable because OCR is not installed.")

    detection = DetectionEngine().detect(
        frame=frame,
        face_mesh=face_mesh if body.protect_faces else None,
        ocr_enabled=needs_text,
    )
    if not detection.success:
        logger.error(f"Protect endpoint: detection failed — {detection.error}")
        raise _fail(500, "PROTECTION_FAILED", "Could not apply protections. Please try again.")

    classification = (
        SignalClassificationEngine().classify(detection.regions)
        if body.protect_documents
        else ClassificationResult(success=True, signals=[])
    )

    result = FinalImageBuilder().build(
        image_bytes=frame.content,
        regions=detection.regions,
        classification=classification,
        request=body,
        filename=frame.filename,
    )
    if not result.success or result.image_bytes is None:
        raise _fail(500, "PROTECTION_FAILED", "Could not apply protections. Please try again.")

    logger.info(
        f"Protect endpoint: complete | session={session_id} | "
        f"faces={result.faces_protected} | text={result.text_regions_protected} | "
        f"document_regions={result.document_regions_protected}"
    )

    return Response(
        content=result.image_bytes,
        media_type=result.media_type,
        headers={
            "X-Privo-Faces-Protected": str(result.faces_protected),
            "X-Privo-Text-Regions-Protected": str(result.text_regions_protected),
            "X-Privo-Document-Regions-Protected": str(result.document_regions_protected),
            "Cache-Control": "no-store",
        },
    )
"""
app/pipeline/export/final_image_builder.py

Applies protections to the original image and returns the final protected
image as bytes. Nothing is written to disk. Re-encoding drops all metadata.

Never raises — returns BuildResult(success=False) on any error.
"""

import os
from typing import List, Literal, Optional

import cv2
import numpy as np
from pydantic import BaseModel

from app.core.logging import get_logger
from app.pipeline.detection.roi_manager import DetectedRegion, RegionType
from app.pipeline.classification.signal_classification import ClassificationResult
from app.pipeline.protection.face_protection import FaceProtection, FaceProtectionMode
from app.pipeline.protection.text_protection import TextProtection, TextProtectionMode
from app.pipeline.protection.document_protection import (
    DocumentProtection,
    DOCUMENT_SIGNAL_TYPES,
)

logger = get_logger(__name__)


class ProtectionRequest(BaseModel):
    protect_faces: bool = True
    face_mode: Literal["blur", "pixelate", "mask"] = "blur"
    protect_text: bool = False
    text_mode: Literal["redact", "blur"] = "redact"
    protect_documents: bool = True


class BuildResult(BaseModel):
    success: bool = False
    image_bytes: Optional[bytes] = None
    media_type: Optional[str] = None
    faces_protected: int = 0
    text_regions_protected: int = 0
    document_regions_protected: int = 0
    error: Optional[str] = None


class FinalImageBuilder:

    def build(
        self,
        image_bytes: bytes,
        regions: List[DetectedRegion],
        classification: ClassificationResult,
        request: ProtectionRequest,
        filename: Optional[str] = None,
    ) -> BuildResult:
        try:
            image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                return BuildResult(error="Could not decode image bytes.")

            faces_protected = 0
            if request.protect_faces:
                face_regions = [r for r in regions if r.region_type == RegionType.FACE]
                if face_regions:
                    image = FaceProtection().apply(
                        image, face_regions, FaceProtectionMode(request.face_mode)
                    )
                    faces_protected = len(face_regions)

            text_regions = [r for r in regions if r.region_type == RegionType.TEXT]

            document_protected = 0
            if (
                request.protect_documents
                and text_regions
                and any(s.signal_type in DOCUMENT_SIGNAL_TYPES for s in classification.signals)
            ):
                image = DocumentProtection().apply(image, regions, classification)
                document_protected = len(text_regions)

            text_protected = 0
            if request.protect_text and text_regions and not document_protected:
                image = TextProtection().apply(
                    image, text_regions, TextProtectionMode(request.text_mode)
                )
                text_protected = len(text_regions)

            ext, params, media_type = self._output_format(filename)
            ok, buffer = cv2.imencode(ext, image, params)
            if not ok:
                return BuildResult(error="Could not encode protected image.")

            logger.info(
                f"Final Image Builder: complete | faces={faces_protected} | "
                f"text={text_protected} | document_regions={document_protected} | "
                f"bytes={buffer.nbytes}"
            )
            return BuildResult(
                success=True,
                image_bytes=buffer.tobytes(),
                media_type=media_type,
                faces_protected=faces_protected,
                text_regions_protected=text_protected,
                document_regions_protected=document_protected,
            )

        except Exception as exc:
            logger.error(f"Final Image Builder: error — {exc}", exc_info=True)
            return BuildResult(error="Image build failed.")

    @staticmethod
    def _output_format(filename: Optional[str]):
        ext = os.path.splitext(filename or "")[1].lower()
        if ext == ".png":
            return ".png", [cv2.IMWRITE_PNG_COMPRESSION, 3], "image/png"
        return ".jpg", [cv2.IMWRITE_JPEG_QUALITY, 95], "image/jpeg"
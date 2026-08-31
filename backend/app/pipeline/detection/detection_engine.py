"""
app/pipeline/detection/detection_engine.py

Orchestrates three detectors against a PrivoFrame:
    - MediaPipe Face Mesh  → face regions
    - OpenCV QRCodeDetector → QR code regions + decoded content
    - Pytesseract          → text regions + extracted text

Models are loaded once at startup in main.py and passed in.
This engine holds no model state itself.

Never raises — returns DetectionResult(success=False) on any error.
"""

import numpy as np
import cv2

from typing import Optional, List, TYPE_CHECKING
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.pipeline.intake.trigger import PrivoFrame
from app.pipeline.detection.roi_manager import (
    ROIManager,
    DetectedRegion,
    RegionType,
)

if TYPE_CHECKING:
    import mediapipe as mp

logger = get_logger(__name__)


class DetectionResult(BaseModel):
    """Output of DetectionEngine.detect()."""

    model_config = {"arbitrary_types_allowed": True}

    success: bool = Field(default=False)
    regions: List[DetectedRegion] = Field(default_factory=list)
    image_width: int = Field(default=0)
    image_height: int = Field(default=0)
    face_count: int = Field(default=0)
    qr_count: int = Field(default=0)
    text_count: int = Field(default=0)
    error: Optional[str] = None


class DetectionEngine:
    """
    Runs all detectors against a PrivoFrame.

    USAGE
    -----
    engine = DetectionEngine()
    result = engine.detect(
        frame=session.privo_frame,
        face_mesh=app.state.face_mesh,
        ocr_enabled=True,
    )
    """

    def detect(
        self,
        frame: PrivoFrame,
        face_mesh=None,
        ocr_enabled: bool = True,
    ) -> DetectionResult:
        """
        Parameters
        ----------
        frame      : PrivoFrame — source image bytes
        face_mesh  : mediapipe FaceMesh instance from app.state
        ocr_enabled: whether to run Pytesseract (can disable for speed)
        """
        logger.info(
            f"Detection Engine: starting | "
            f"file='{frame.filename}' | "
            f"size={frame.size_bytes} bytes"
        )

        try:
            # Decode bytes → OpenCV matrix (BGR)
            img_array = np.frombuffer(frame.content, dtype=np.uint8)
            image_bgr = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

            if image_bgr is None:
                return DetectionResult(
                    success=False,
                    error="OpenCV could not decode image bytes."
                )

            h, w = image_bgr.shape[:2]
            roi_manager = ROIManager()

            # ── Face detection ─────────────────────────────────
            if face_mesh is not None:
                face_regions = self._detect_faces(image_bgr, face_mesh, w, h)
                roi_manager.add_regions(face_regions)
            else:
                logger.warning("Detection Engine: face_mesh not provided — skipping face detection")

            # ── QR detection ───────────────────────────────────
            qr_regions = self._detect_qr(image_bgr)
            roi_manager.add_regions(qr_regions)

            # ── Text detection ─────────────────────────────────
            if ocr_enabled:
                text_regions = self._detect_text(image_bgr)
                roi_manager.add_regions(text_regions)

            summary = roi_manager.summary()

            logger.info(
                f"Detection Engine: complete | "
                f"faces={summary['faces']} | "
                f"qr={summary['qr_codes']} | "
                f"text={summary['text']}"
            )

            return DetectionResult(
                success=True,
                regions=roi_manager.get_all(),
                image_width=w,
                image_height=h,
                face_count=summary["faces"],
                qr_count=summary["qr_codes"],
                text_count=summary["text"],
            )

        except Exception as exc:
            logger.error(
                f"Detection Engine: unexpected error — {exc}",
                exc_info=True
            )
            return DetectionResult(
                success=False,
                error=f"Detection failed: {str(exc)}"
            )

    # ── PRIVATE DETECTORS ──────────────────────────────────────

    def _detect_faces(
        self,
        image_bgr: np.ndarray,
        face_mesh,
        img_w: int,
        img_h: int,
    ) -> List[DetectedRegion]:
        """
        MediaPipe Face Mesh detection.
        Returns one DetectedRegion per detected face.
        Confidence is always 1.0 — MediaPipe does not expose
        a per-detection score from FaceMesh results.
        """
        regions: List[DetectedRegion] = []

        try:
            # MediaPipe expects RGB
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(image_rgb)

            if not results.multi_face_landmarks:
                return regions

            for face_landmarks in results.multi_face_landmarks:
                # Extract bounding box from normalised landmark coordinates
                xs = [lm.x for lm in face_landmarks.landmark]
                ys = [lm.y for lm in face_landmarks.landmark]

                x_min = int(min(xs) * img_w)
                y_min = int(min(ys) * img_h)
                x_max = int(max(xs) * img_w)
                y_max = int(max(ys) * img_h)

                # Clamp to image bounds
                x_min = max(0, x_min)
                y_min = max(0, y_min)
                x_max = min(img_w, x_max)
                y_max = min(img_h, y_max)

                regions.append(DetectedRegion(
                    x=x_min,
                    y=y_min,
                    width=x_max - x_min,
                    height=y_max - y_min,
                    region_type=RegionType.FACE,
                    confidence=1.0,
                ))

            logger.debug(f"Face detector: {len(regions)} face(s) found")

        except Exception as exc:
            logger.error(f"Face detector error: {exc}", exc_info=True)

        return regions

    def _detect_qr(self, image_bgr: np.ndarray) -> List[DetectedRegion]:
        """
        OpenCV QRCodeDetector.
        Returns one DetectedRegion per detected QR code or barcode.
        Content field contains the decoded string.
        """
        regions: List[DetectedRegion] = []

        try:
            detector = cv2.QRCodeDetector()
            data, points, _ = detector.detectAndDecode(image_bgr)

            if points is not None and data:
                pts = points[0].astype(int)
                x_min = int(pts[:, 0].min())
                y_min = int(pts[:, 1].min())
                x_max = int(pts[:, 0].max())
                y_max = int(pts[:, 1].max())

                regions.append(DetectedRegion(
                    x=x_min,
                    y=y_min,
                    width=x_max - x_min,
                    height=y_max - y_min,
                    region_type=RegionType.QR_CODE,
                    confidence=1.0,
                    content=data,
                ))
                logger.debug(f"QR detector: found QR — content='{data[:40]}'")

        except Exception as exc:
            logger.error(f"QR detector error: {exc}", exc_info=True)

        return regions

    def _detect_text(self, image_bgr: np.ndarray) -> List[DetectedRegion]:
        """
        Pytesseract text region detection.

        Uses image_to_data() to get bounding boxes for each word.
        Filters by confidence threshold to reduce false positives.
        Groups overlapping word boxes into paragraph-level regions.

        Requires Tesseract binary on system PATH.
        Gracefully returns [] if Tesseract is not installed.
        """
        regions: List[DetectedRegion] = []

        try:
            import pytesseract
            from pytesseract import Output

            # Tesseract works better on grayscale
            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

            data = pytesseract.image_to_data(
                gray,
                output_type=Output.DICT,
                config="--psm 11",
                # --psm 11: sparse text — finds text anywhere in image
                # without assuming a reading order or layout structure.
                # Better for photos than the default document mode.
            )

            CONFIDENCE_THRESHOLD = 60
            # Tesseract confidence 0–100.
            # Below 60 is typically noise or non-text regions.
            # Adjust down if missing real text, up to reduce false positives.

            n_boxes = len(data["text"])
            for i in range(n_boxes):
                conf = int(data["conf"][i])
                text = data["text"][i].strip()

                if conf < CONFIDENCE_THRESHOLD or not text:
                    continue

                x = data["left"][i]
                y = data["top"][i]
                w = data["width"][i]
                h = data["height"][i]

                if w <= 0 or h <= 0:
                    continue

                regions.append(DetectedRegion(
                    x=x,
                    y=y,
                    width=w,
                    height=h,
                    region_type=RegionType.TEXT,
                    confidence=conf / 100.0,
                    content=text,
                ))

            logger.debug(f"Text detector: {len(regions)} text region(s) found")

        except ImportError:
            logger.warning(
                "Text detector: pytesseract not installed — skipping text detection. "
                "Install: pip install pytesseract and the Tesseract binary."
            )
        except Exception as exc:
            logger.error(f"Text detector error: {exc}", exc_info=True)

        return regions
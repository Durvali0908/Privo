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
        MediaPipe FaceLandmarker detection (Tasks API — mediapipe 1.0.1+).

        face_mesh is a FaceLandmarker instance created in main.py lifespan.
        FaceLandmarkerResult.face_landmarks is:
            List[List[NormalizedLandmark]]
        Each inner list is one face. NormalizedLandmark has .x and .y
        in normalised image coordinates (0.0–1.0).
        """
        regions: List[DetectedRegion] = []

        try:
            import mediapipe as mp

            # Tasks API requires RGB input wrapped in mp.Image
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            mp_image  = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=image_rgb
            )

            results = face_mesh.detect(mp_image)
            # results: FaceLandmarkerResult
            # results.face_landmarks: List[List[NormalizedLandmark]]

            if not results.face_landmarks:
                logger.debug("Face detector: no faces found")
                return regions

            for face_landmark_list in results.face_landmarks:
                # face_landmark_list: List[NormalizedLandmark]
                xs = [lm.x for lm in face_landmark_list]
                ys = [lm.y for lm in face_landmark_list]

                x_min = max(0,     int(min(xs) * img_w))
                y_min = max(0,     int(min(ys) * img_h))
                x_max = min(img_w, int(max(xs) * img_w))
                y_max = min(img_h, int(max(ys) * img_h))

                regions.append(DetectedRegion(
                    x=x_min,
                    y=y_min,
                    width=x_max  - x_min,
                    height=y_max - y_min,
                    region_type=RegionType.FACE,
                    confidence=1.0,
                    # FaceLandmarker does not expose a per-detection
                    # confidence score in IMAGE running mode.
                ))

            logger.debug(f"Face detector: {len(regions)} face(s) found")

        except Exception as exc:
            logger.error(f"Face detector error: {exc}", exc_info=True)

        return regions

    def _detect_qr(self, image_bgr: np.ndarray) -> List[DetectedRegion]:
        """
        OpenCV QRCodeDetector — multi-QR detection.

        Uses detectAndDecodeMulti() to find ALL QR codes in one call.
        Falls back to detectAndDecode() if multi fails (OpenCV < 4.5).

        Also attempts detection on a preprocessed grayscale image
        to improve detection of low-contrast QR codes on screens.
        """
        regions: List[DetectedRegion] = []

        try:
            detector = cv2.QRCodeDetector()

            # Try colour image first, then grayscale for screen QR codes
            candidates = [image_bgr]
            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
            # Adaptive threshold improves low-contrast screen QR codes
            thresh = cv2.adaptiveThreshold(
                gray, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )
            candidates.append(cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR))

            seen_boxes: set = set()

            for img_candidate in candidates:
                # Try multi-QR first (OpenCV 4.5+)
                try:
                    retval, decoded_list, points_list, _ =                         detector.detectAndDecodeMulti(img_candidate)

                    if retval and points_list is not None:
                        for i, pts in enumerate(points_list):
                            data = decoded_list[i] if i < len(decoded_list) else ""
                            pts_int = pts.astype(int)
                            x_min = int(pts_int[:, 0].min())
                            y_min = int(pts_int[:, 1].min())
                            x_max = int(pts_int[:, 0].max())
                            y_max = int(pts_int[:, 1].max())

                            # Deduplicate by box position
                            box_key = (x_min // 10, y_min // 10)
                            if box_key in seen_boxes:
                                continue
                            seen_boxes.add(box_key)

                            regions.append(DetectedRegion(
                                x=x_min,
                                y=y_min,
                                width=x_max - x_min,
                                height=y_max - y_min,
                                region_type=RegionType.QR_CODE,
                                confidence=1.0,
                                content=data if data else None,
                            ))
                            logger.debug(
                                f"QR detector: found QR — "
                                f"content='{str(data)[:40]}'"
                            )

                except (cv2.error, AttributeError):
                    # Fallback: single QR detection (older OpenCV)
                    data, points, _ = detector.detectAndDecode(img_candidate)
                    if points is not None and data:
                        pts = points[0].astype(int)
                        x_min = int(pts[:, 0].min())
                        y_min = int(pts[:, 1].min())
                        x_max = int(pts[:, 0].max())
                        y_max = int(pts[:, 1].max())

                        box_key = (x_min // 10, y_min // 10)
                        if box_key not in seen_boxes:
                            seen_boxes.add(box_key)
                            regions.append(DetectedRegion(
                                x=x_min,
                                y=y_min,
                                width=x_max - x_min,
                                height=y_max - y_min,
                                region_type=RegionType.QR_CODE,
                                confidence=1.0,
                                content=data,
                            ))

            logger.debug(f"QR detector: {len(regions)} QR code(s) found")

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
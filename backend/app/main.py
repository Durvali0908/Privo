from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.api.v1.router import v1_router

setup_logging(log_level="DEBUG" if settings.debug else "INFO")
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ──────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info(f"  {settings.app_name} v{settings.app_version} starting")
    logger.info("=" * 60)

    app.state.face_mesh = None
    try:
        import mediapipe as mp
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python import BaseOptions
        import os

        model_path = settings.face_landmarker_model_path

        if not os.path.exists(model_path):
            logger.warning(
                f"FaceLandmarker model not found at '{model_path}'. "
                f"Download from: https://storage.googleapis.com/mediapipe-models/"
                f"face_landmarker/face_landmarker/float16/1/face_landmarker.task"
            )
        else:
            options = vision.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=model_path),
                running_mode=vision.RunningMode.IMAGE,
                num_faces=10,
                min_face_detection_confidence=0.5,
                min_face_presence_confidence=0.5,
                min_tracking_confidence=0.5,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=False,
            )
            app.state.face_mesh = vision.FaceLandmarker.create_from_options(options)
            logger.info("MediaPipe FaceLandmarker loaded (Tasks API)")

    except ImportError as exc:
        logger.warning(f"mediapipe not installed — face detection disabled: {exc}")
    except Exception as exc:
        logger.error(f"FaceLandmarker load failed: {exc}", exc_info=True)

    logger.info(f"CORS origins : {settings.allowed_origins}")
    logger.info(f"Max file size: {settings.max_file_size_mb} MB")
    logger.info("-" * 60)
    logger.info("Privo backend is ready.")
    logger.info("-" * 60)

    yield

    # ── SHUTDOWN ─────────────────────────────────────────────────
    if hasattr(app.state, "face_mesh") and app.state.face_mesh is not None:
        app.state.face_mesh.close()
        logger.info("MediaPipe FaceLandmarker released")
    logger.info("Privo backend shutting down.")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=settings.app_description,
    debug=settings.debug,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "Authorization"],
)

app.include_router(v1_router)


@app.get("/", tags=["Root"])
async def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "description": settings.app_description,
        "status": "running",
        "docs": "/docs",
    }
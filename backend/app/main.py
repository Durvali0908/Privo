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

    # Load MediaPipe FaceMesh once — shared across all requests via app.state
    try:
        import mediapipe as mp
        app.state.face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=True,
            # static_image_mode=True: each call processes an independent image.
            # False is for video streams where the same face persists frame to frame.
            max_num_faces=10,
            refine_landmarks=False,
            # refine_landmarks=False: skips iris landmarks (468→478).
            # We only need the face bounding box, not iris precision.
            # Saves ~20ms per image on the i3.
            min_detection_confidence=0.5,
        )
        logger.info("MediaPipe FaceMesh loaded")
    except ImportError:
        app.state.face_mesh = None
        logger.warning("mediapipe not installed — face detection disabled")
    except Exception as exc:
        app.state.face_mesh = None
        logger.error(f"FaceMesh load failed: {exc}")

    logger.info(f"CORS origins : {settings.allowed_origins}")
    logger.info(f"Max file size: {settings.max_file_size_mb} MB")
    logger.info("-" * 60)
    logger.info("Privo backend is ready.")
    logger.info("-" * 60)

    yield

    # ── SHUTDOWN ─────────────────────────────────────────────────
    if hasattr(app.state, "face_mesh") and app.state.face_mesh is not None:
        app.state.face_mesh.close()
        logger.info("MediaPipe FaceMesh released")

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
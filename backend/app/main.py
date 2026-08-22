"""
backend/app/main.py

PURPOSE
-------
The FastAPI application entry point.

This file creates the FastAPI app instance, configures middleware,
mounts the API router, and defines the application lifecycle.

It is the file Uvicorn runs:
    uvicorn app.main:app --reload

Everything else in the backend exists to be assembled here.

─────────────────────────────────────────────────────────────────────
STARTUP SEQUENCE
─────────────────────────────────────────────────────────────────────
1. Python imports this file
2. setup_logging() runs          → logging system is active
3. FastAPI app object is created → settings applied from config.py
4. CORS middleware is attached   → React at localhost:5173 is allowed
5. v1_router is mounted          → /api/v1/analyze is registered
6. Uvicorn starts the HTTP server

After step 6, the backend is live and React can send requests.

─────────────────────────────────────────────────────────────────────
RUNNING THE BACKEND
─────────────────────────────────────────────────────────────────────
From the backend/ directory, with your .venv active:

    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

    app.main  → the Python module path (app/main.py)
    app       → the FastAPI instance variable name inside that module
    --reload  → restart on file changes (development only)
    --host 0.0.0.0  → accept connections from any network interface
                      needed for PWA testing on a phone on the same WiFi
    --port 8000     → the port React's api.ts calls

─────────────────────────────────────────────────────────────────────
HOW THIS FILE COMMUNICATES WITH OTHER MODULES
─────────────────────────────────────────────────────────────────────
Imports and calls:
    app/core/logging.py   → setup_logging() called first, before anything else
    app/core/config.py    → settings used for app metadata and CORS origins
    app/api/v1/router.py  → v1_router mounted on the FastAPI app

Used by:
    Uvicorn → runs `app` (the FastAPI instance)
    Tests   → import `app` and wrap with TestClient

─────────────────────────────────────────────────────────────────────
FUTURE ADDITIONS TO THIS FILE
─────────────────────────────────────────────────────────────────────
Startup block (lifespan):
    - Load YOLO model weights into memory (Week 3)
    - Warm up MediaPipe Face Mesh (Week 3)
    - Load EasyOCR models (Week 3)
    These are expensive one-time operations. Loading them at startup
    means the first request is not slow. Loading inside the endpoint
    would penalise every cold request.

Custom exception handler:
    - Intercept HTTPException and return flat ErrorResponse body
      without FastAPI's { "detail": ... } wrapper (see analyze.py)
    - Add here when the frontend team requests a consistent flat format

Additional middleware:
    - Request ID middleware: tag every request with a UUID for tracing
    - Timing middleware: log how long each request takes
    - Rate limiting: prevent abuse of the analysis endpoint
"""

from contextlib import asynccontextmanager
# asynccontextmanager: A decorator that turns an async generator function
# into an async context manager.
# Used here to define the lifespan of the FastAPI application.
#
# WHAT IS A CONTEXT MANAGER?
# A context manager is something used with Python's `with` statement:
#     with open("file.txt") as f:
#         ...
# Code before `yield` runs on entry. Code after `yield` runs on exit.
# asynccontextmanager does the same thing but for async code.
#
# WHAT IS THE lifespan CONTEXT MANAGER?
# FastAPI's lifespan parameter accepts an async context manager.
# Code before yield → runs at startup (server starting)
# Code after yield  → runs at shutdown (server stopping)
# This replaces the older @app.on_event("startup") pattern,
# which is deprecated in modern FastAPI.

from fastapi import FastAPI
# FastAPI: The main application class.
# FastAPI() creates the application instance that Uvicorn runs.
# It handles: routing, middleware, dependency injection,
# automatic OpenAPI/Swagger documentation, request parsing,
# response serialisation, and error handling.

from fastapi.middleware.cors import CORSMiddleware
# CORSMiddleware: FastAPI's built-in CORS middleware.
#
# WHAT IS CORS?
# CORS (Cross-Origin Resource Sharing) is a browser security feature.
# When React at http://localhost:5173 sends a request to FastAPI at
# http://localhost:8000, the browser sees two different "origins"
# (different ports = different origins) and blocks the request by default.
#
# CORSMiddleware tells the browser: "these origins are trusted,
# allow their requests through."
#
# Without CORS configured:
#   React sends POST /api/v1/analyze
#   Browser blocks it before it reaches FastAPI
#   React receives a network error, not a response
#   This is one of the most common "why isn't my API working" mistakes.

from app.core.config import settings
# settings: Central configuration singleton.
# We use:
#   settings.app_name          → FastAPI app title
#   settings.app_version       → FastAPI app version
#   settings.app_description   → FastAPI app description
#   settings.debug             → FastAPI debug mode
#   settings.allowed_origins   → CORS trusted origins

from app.core.logging import setup_logging, get_logger
# setup_logging: Configures the entire logging system.
#   Must be called before any other import that might log,
#   otherwise early log messages use Python's default format.
# get_logger: Returns a named logger for this module.

from app.api.v1.router import v1_router
# v1_router: The assembled v1 API router from router.py.
#   Contains all /api/v1/* routes.
#   Mounting it registers all routes with the FastAPI app.


# ─────────────────────────────────────────────────────────────────
# LOGGING INITIALISATION
# Must happen before anything else logs.
# ─────────────────────────────────────────────────────────────────

setup_logging(log_level="DEBUG" if settings.debug else "INFO")
# "DEBUG" in development: see every log line from every module.
# "INFO" in production: only see meaningful operational messages.
# settings.debug is True by default (set in config.py).
# Change it to False in your .env for production-like output.

logger = get_logger(__name__)
# __name__ = "app.main"
# Logger name = "privo.app.main"


# ─────────────────────────────────────────────────────────────────
# APPLICATION LIFESPAN
# Code here runs at startup (before yield) and shutdown (after yield).
# ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    WHAT THIS CONTROLS
    ------------------
    Everything before `yield` runs when the server starts.
    Everything after `yield` runs when the server shuts down.
    The `yield` itself is where the server runs and handles requests.

    Visualised:
        Server starts
            ↓
        [startup code runs]
            ↓
        yield  ← server is live here, handling requests
            ↓
        [shutdown code runs]
            ↓
        Server stops

    WHY async?
    ----------
    Some startup operations are async — for example, loading a model
    from disk or making an async database connection. The lifespan
    manager must be async to support these. Even if no startup code
    is async right now, declaring it async means we never need to
    change the signature when async startup tasks are added.

    PARAMETERS
    ----------
    app : FastAPI
        The FastAPI application instance. Passed in automatically
        by FastAPI when the lifespan is registered. You can use it
        to store shared state: app.state.model = loaded_model
        Other parts of the app then read: request.app.state.model
        This is the correct way to share expensive resources (like
        ML models) across requests without global variables.

    WEEK 1 STARTUP
    --------------
    Only logging confirmation. No heavy operations yet.

    FUTURE STARTUP (Week 3+)
    ------------------------
    app.state.yolo_model      = load_yolo_model()
    app.state.mediapipe_model = load_mediapipe()
    app.state.ocr_engine      = load_easyocr()

    These will be loaded here so the first analysis request is not slow.
    The Detection Engine will read: request.app.state.yolo_model
    """

    # ── STARTUP ───────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info(f"  {settings.app_name} v{settings.app_version} starting")
    logger.info(f"  {settings.app_description}")
    logger.info("=" * 60)
    logger.info(f"Debug mode   : {settings.debug}")
    logger.info(f"API prefix   : {settings.api_v1_prefix}")
    logger.info(f"CORS origins : {settings.allowed_origins}")
    logger.info(f"Max file size: {settings.max_file_size_mb} MB")
    logger.info(f"Session expiry: {settings.session_expiry_minutes} minutes")
    logger.info("-" * 60)
    logger.info("Privo backend is ready.")
    logger.info("-" * 60)

    yield
    # The server runs here.
    # FastAPI handles all incoming requests between startup and shutdown.
    # When Uvicorn receives a shutdown signal (Ctrl+C or SIGTERM),
    # execution resumes after this yield.

    # ── SHUTDOWN ──────────────────────────────────────────────────
    logger.info("-" * 60)
    logger.info("Privo backend shutting down.")
    logger.info("-" * 60)
    # Future: release ML model resources, close database connections,
    # flush any pending analytics data to persistent storage.


# ─────────────────────────────────────────────────────────────────
# FASTAPI APPLICATION
# The app instance that Uvicorn runs.
# ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    # title: Shown in the Swagger UI header at /docs.
    # "Privo" appears as the API title in the documentation page.

    version=settings.app_version,
    # version: Shown in the Swagger UI alongside the title.
    # "0.1.0" in development.

    description=settings.app_description,
    # description: Shown below the title in Swagger UI.
    # "Privacy Intelligence Assistant"

    debug=settings.debug,
    # debug=True: FastAPI includes detailed error information in
    # responses when an unhandled exception occurs.
    # debug=False in production: hides internal details from users.

    lifespan=lifespan,
    # lifespan: Registers the async context manager we defined above.
    # FastAPI calls it when the server starts and stops.
    # This replaces the deprecated @app.on_event pattern.

    docs_url="/docs",
    # docs_url: Where the Swagger UI is served.
    # Visit http://localhost:8000/docs to see and test all endpoints.
    # You can test POST /api/v1/analyze directly from the browser here.

    redoc_url="/redoc",
    # redoc_url: An alternative API documentation UI.
    # Visit http://localhost:8000/redoc for a different documentation style.

    openapi_url="/openapi.json",
    # openapi_url: The raw OpenAPI schema (JSON format).
    # Tools like Postman can import this to auto-generate a collection.
    # Future: The React frontend could generate TypeScript types from this.
)


# ─────────────────────────────────────────────────────────────────
# CORS MIDDLEWARE
# Must be added before mounting routers.
# ─────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    # CORSMiddleware: The middleware class to add.

    allow_origins=settings.allowed_origins,
    # allow_origins: List of trusted origins.
    # From config.py: ["http://localhost:5173", "http://localhost:3000"]
    # localhost:5173 → Vite dev server (React)
    # localhost:3000 → alternative dev server port
    #
    # WHY NOT allow_origins=["*"] (allow all)?
    # "*" would allow any website to call Privo's API.
    # An attacker could build a malicious site that silently uploads
    # a user's images to Privo without their knowledge.
    # Restricting to known origins prevents this.
    # In production, replace localhost URLs with your actual domain.

    allow_credentials=True,
    # allow_credentials=True: Allows the browser to send cookies
    # and authentication headers with cross-origin requests.
    # Week 1 uses no authentication, but this is set correctly now
    # so that adding auth later does not require CORS reconfiguration.
    #
    # IMPORTANT: allow_credentials=True is incompatible with
    # allow_origins=["*"]. You must list specific origins when
    # credentials are allowed. We do this correctly above.

    allow_methods=["GET", "POST", "OPTIONS"],
    # allow_methods: Which HTTP methods are permitted from allowed origins.
    # GET    → future: session status, gallery retrieval
    # POST   → analyze, protect
    # OPTIONS→ required for CORS preflight requests.
    #
    # WHAT IS A PREFLIGHT REQUEST?
    # Before sending a POST with custom headers, browsers send an
    # OPTIONS request to ask: "is this cross-origin POST allowed?"
    # The server must respond correctly to OPTIONS for the actual
    # POST to be sent. CORSMiddleware handles this automatically
    # when OPTIONS is in allow_methods.

    allow_headers=["Content-Type", "Accept", "Authorization"],
    # allow_headers: Which request headers are permitted.
    # Content-Type  → required for multipart/form-data uploads
    # Accept        → React may send Accept: application/json
    # Authorization → needed when authentication is added later
)


# ─────────────────────────────────────────────────────────────────
# MOUNT ROUTERS
# ─────────────────────────────────────────────────────────────────

app.include_router(v1_router)
# Mounts the v1 router and all its routes onto the FastAPI app.
# v1_router has prefix="/api/v1" set internally.
# After this line, the following routes are live:
#   POST /api/v1/analyze
#
# We do not add a prefix here because v1_router already declares its
# own prefix. Adding prefix="/api/v1" here as well would produce:
#   /api/v1/api/v1/analyze   ← wrong, double prefix
# The router is self-contained. main.py includes it as-is.


# ─────────────────────────────────────────────────────────────────
# ROOT ROUTE
# A simple health-check endpoint at the root path.
# ─────────────────────────────────────────────────────────────────

@app.get("/", tags=["Root"])
async def root():
    """
    Root health check.

    Returns basic application information.
    Used to verify the server is running before testing the full pipeline.

    Visit http://localhost:8000/ in a browser to confirm the backend is live.

    FUTURE
    ------
    A dedicated /api/v1/health endpoint will replace this with a
    richer health check: database connectivity, model loading status,
    active session count, memory usage, and uptime.
    """
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "description": settings.app_description,
        "status": "running",
        "docs": "/docs"
    }
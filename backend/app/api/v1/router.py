"""
backend/app/api/v1/router.py

PURPOSE
-------
Assembles all API version 1 endpoint routers into a single router
that main.py can mount with one line.

This file is the routing switchboard for Privo's v1 API. It does
no data processing and contains no business logic. Its only job is
to declare which endpoint routers exist and what prefix each one
lives under.

─────────────────────────────────────────────────────────────────────
WHY THIS FILE EXISTS
─────────────────────────────────────────────────────────────────────
Without this file, main.py would need to import every endpoint
router individually and mount each one separately:

    # Without router.py (do not do this):
    from app.api.v1.endpoints.analyze  import router as analyze_router
    from app.api.v1.endpoints.protect  import router as protect_router
    from app.api.v1.endpoints.gallery  import router as gallery_router
    from app.api.v1.endpoints.health   import router as health_router

    app.include_router(analyze_router, prefix="/api/v1")
    app.include_router(protect_router, prefix="/api/v1")
    app.include_router(gallery_router, prefix="/api/v1")
    app.include_router(health_router,  prefix="/api/v1")

main.py is the application entry point — it handles startup, CORS,
middleware, and lifecycle events. It should not be concerned with
which individual endpoint files exist.

With router.py, main.py does one thing:

    from app.api.v1.router import v1_router
    app.include_router(v1_router)

Adding a new endpoint in the future means adding two lines here.
main.py never changes.

─────────────────────────────────────────────────────────────────────
PREFIX STACKING — HOW ROUTES ARE ASSEMBLED
─────────────────────────────────────────────────────────────────────
Prefixes are additive across layers. Each layer declares only its
own segment — none hardcodes the full path.

    main.py mounts v1_router with no extra prefix
        v1_router has prefix="/api/v1"
            analyze sub-router has prefix="/analyze"
                route decorated with "/"  → not used in Week 1
                route decorated with "/analyze"  (but included as "")

Wait — let me be precise about how this actually works:

    v1_router = APIRouter(prefix="/api/v1")
    v1_router.include_router(analyze.router, prefix="/analyze")

    analyze.router has:
        @router.post("/analyze")   ← this is the route path on the sub-router

    COMBINED RESULT:
        /api/v1  +  /analyze  +  /analyze  = /api/v1/analyze/analyze  ✗ WRONG

    The correct pattern is:
        analyze.router has @router.post("")  (empty string, meaning "root of this router")
        v1_router.include_router(analyze.router, prefix="/analyze")
        RESULT: /api/v1/analyze  ✓

    BUT — we decorated the route as @router.post("/analyze") in analyze.py.
    So the correct include here is prefix="" (no additional prefix):
        v1_router.include_router(analyze.router, prefix="")
        RESULT: /api/v1/analyze  ✓

    This is consistent with how analyze.py was written.
    The route is self-contained at /analyze within the router.
    The v1 router adds /api/v1. Final: /api/v1/analyze.

─────────────────────────────────────────────────────────────────────
HOW THIS FILE COMMUNICATES WITH OTHER MODULES
─────────────────────────────────────────────────────────────────────
Imports from:
    app/api/v1/endpoints/analyze.py → analyze.router

Imported by:
    app/main.py → mounts v1_router on the FastAPI app

Future endpoints to add here (not yet):
    app/api/v1/endpoints/health.py   → health check route
    app/api/v1/endpoints/session.py  → session status route
    app/api/v1/endpoints/protect.py  → protection application route
    app/api/v1/endpoints/gallery.py  → Privo gallery route
"""

from fastapi import APIRouter
# APIRouter: FastAPI's router class.
# Used here to create the top-level v1 router that assembles
# all endpoint sub-routers under the /api/v1 prefix.

from app.api.v1.endpoints import analyze
# analyze: The analyze endpoint module.
# We import the module (not just the router) so the import is
# explicit about which file it comes from.
# analyze.router is the APIRouter instance defined in that file.
#
# WHY IMPORT THE MODULE AND NOT JUST THE ROUTER?
# -----------------------------------------------
# from app.api.v1.endpoints.analyze import router
# works fine but creates an ambiguous name: `router` could be
# any router from any module. Reading the include_router calls
# below, you immediately see: "analyze.router" → this is the
# router from the analyze module. No ambiguity.

from app.core.logging import get_logger
# get_logger: Logging factory. Used to confirm router assembly.

logger = get_logger(__name__)
# __name__ = "app.api.v1.router"
# Logger name = "privo.app.api.v1.router"


# ─────────────────────────────────────────────────────────────────
# V1 ROUTER
# The single router that main.py mounts.
# All v1 API routes live under /api/v1.
# ─────────────────────────────────────────────────────────────────

v1_router = APIRouter(prefix="/api/v1")
# prefix="/api/v1":
#   Every route included in this router automatically gets /api/v1
#   prepended to its path.
#
# WHY VERSION THE API?
# ---------------------
# /api/v1/analyze means this is version 1 of the analyze endpoint.
# When Privo's API changes in a breaking way in the future, a new
# /api/v2/analyze can be added without removing /api/v1/analyze.
# Existing clients (older versions of the React app) continue working
# on v1 while new clients use v2. The version prefix makes this
# migration path possible with zero disruption.
#
# WHY prefix ON THE ROUTER AND NOT IN main.py?
# ---------------------------------------------
# The alternative is: app.include_router(v1_router, prefix="/api/v1")
# Both work. Putting the prefix on the router means the router is
# self-contained — it knows its own address. This makes the router
# independently testable: you can mount it at a test prefix without
# changing the router definition.


# ─────────────────────────────────────────────────────────────────
# INCLUDE ENDPOINT ROUTERS
# Each line below registers one endpoint file's routes.
# ─────────────────────────────────────────────────────────────────

v1_router.include_router(
    analyze.router,
    prefix="",
    # prefix="":
    #   analyze.router already declares its route as @router.post("/analyze").
    #   Adding another prefix here would double it: /api/v1/analyze/analyze.
    #   Empty string means: include as-is, no additional prefix.
    #   Final route: /api/v1  +  ""  +  "/analyze"  =  /api/v1/analyze  ✓

    tags=["Analysis"]
    # tags: Groups this router's routes under the "Analysis" section
    # in FastAPI's auto-generated Swagger UI at /docs.
    # When Privo has many endpoints, tags create a clean, browsable
    # API documentation structure.
)

# ─── Future routers (not yet implemented) ─────────────────────────
# Add each new endpoint file here when its week arrives.
# The pattern is always the same two lines:
#
# from app.api.v1.endpoints import health
# v1_router.include_router(health.router, prefix="", tags=["Health"])
#
# from app.api.v1.endpoints import session
# v1_router.include_router(session.router, prefix="", tags=["Session"])
#
# from app.api.v1.endpoints import protect
# v1_router.include_router(protect.router, prefix="", tags=["Protection"])
#
# from app.api.v1.endpoints import gallery
# v1_router.include_router(gallery.router, prefix="", tags=["Gallery"])
# ──────────────────────────────────────────────────────────────────

logger.debug("API v1 router assembled — routes registered: /api/v1/analyze")
# This log line runs when the module is first imported (at startup).
# If you see it in the terminal, the router assembled without errors.
# Future: update this message as new routes are added.
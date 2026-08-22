"""
backend/app/engine/session.py

PURPOSE
-------
The Session Manager is responsible for creating, storing, retrieving,
and terminating analysis sessions.

Every image analysis in Privo is wrapped in a session. The session is
the identity that connects the Trigger Engine's output to the Detection
Engine's input to the Risk Scoring Engine's results to the final export.

Without sessions, Privo would be a stateless one-shot analyser with no
ability to track pipeline progress, associate results with inputs, or
support a user reviewing and acting on findings before saving.

─────────────────────────────────────────────────────────────────────
WHAT IS A SESSION?
─────────────────────────────────────────────────────────────────────
A session represents one complete analysis lifecycle:

    Image received → Session created → Pipeline runs →
    Results stored in session → User acts → Session closed

A session contains:
- A unique identifier (PRIVO-SESSION-XXXXXXXX)
- The normalised input (PrivoFrame from Trigger Engine)
- The user's settings for this analysis
- Timestamps (created, last updated)
- Current status (pending → processing → complete → terminated)
- Future: detection results, risk scores, heatmap data, export path

─────────────────────────────────────────────────────────────────────
SESSION STORAGE IN WEEK 1
─────────────────────────────────────────────────────────────────────
Sessions are stored in a Python dictionary in memory:
    { "PRIVO-SESSION-A3F8B21C": SessionData(...) }

WHY IN-MEMORY STORAGE FOR WEEK 1?
-----------------------------------
- Zero dependencies: no database, no Redis, no external services
- Zero configuration: works immediately without setup
- Easy to inspect during development
- Fast: dictionary lookups are O(1)

LIMITATIONS OF IN-MEMORY STORAGE
----------------------------------
- Sessions are lost when the server restarts
- Cannot be shared across multiple server processes
- Not suitable for production at scale

FUTURE MIGRATION PATH
----------------------
The SessionManager is designed so that only the storage layer needs
to change — the rest of the application never calls the dict directly.
All reads and writes go through SessionManager methods:
    create_session(), get_session(), terminate_session()

When the time comes to add Redis or a database, only those three
methods change. No other module needs to be updated. This is the
"encapsulation" principle applied to storage.

─────────────────────────────────────────────────────────────────────
SESSION LIFECYCLE (for future modules to understand)
─────────────────────────────────────────────────────────────────────
PENDING     → Session created, pipeline has not started yet
PROCESSING  → Detection Engine / Risk Scoring is running
COMPLETE    → All pipeline stages finished, results available
TERMINATED  → Session explicitly closed by user or timeout

The Memory Engine (future) will move COMPLETE sessions to
persistent storage. The Session Termination Module (future) will
remove TERMINATED sessions from memory to free up space.

─────────────────────────────────────────────────────────────────────
HOW THIS FILE COMMUNICATES WITH OTHER MODULES
─────────────────────────────────────────────────────────────────────
Receives from:
    app/api/v1/endpoints/analyze.py
        → passes result.privo_frame (from Trigger Engine)
        → receives SessionData back

Reads from:
    app/engine/trigger.py
        → PrivoFrame (the normalised input container)
        → InputSource (to tag the session with its origin)

    app/core/config.py
        → default settings values to populate DefaultSettings

Logs via:
    app/core/logging.py
        → records session creation, retrieval, and termination

FUTURE MODULES THAT WILL DEPEND ON THIS FILE
---------------------------------------------
- analyze.py endpoint   → calls create_session(), reads session_id
- metadata_extractor    → calls get_session() to retrieve privo_frame
- detection_engine      → calls get_session() to get frame + settings
- risk_scoring_engine   → reads session.settings.scanning_mode
- memory_engine         → calls get_session(), stores completed data
- analytics_dashboard   → reads session history and status counts
- session_termination   → calls terminate_session() on expiry/user close
"""

import secrets
# secrets: Python's cryptographically secure random number module.
# Part of Python's standard library — no installation needed.
#
# WHY secrets AND NOT random?
# random.random() and random.randint() are designed for simulations
# and games — they use a predictable algorithm (Mersenne Twister).
# Given enough outputs, an attacker can predict future values.
# secrets uses the operating system's entropy source (os.urandom)
# which is unpredictable and safe for security-sensitive tokens.
# Session IDs are security-sensitive: a predictable session ID lets
# an attacker guess another user's session and access their data.
# Using secrets makes session IDs unguessable.
#
# WHY NOT uuid4?
# uuid4() also uses os.urandom internally and is perfectly safe.
# secrets.token_hex() is slightly more explicit about intent
# (it's in the "secrets" module, signalling security purpose)
# and produces a cleaner token format for our use case.

from datetime import datetime, timezone
# datetime: Python's date and time class.
# Used to record when the session was created and last updated.
#
# timezone: Used to create timezone-aware datetime objects.
# We always store UTC timestamps — never local time.
#
# WHY UTC?
# Local time depends on the server's timezone setting, which can
# vary between development (your laptop) and production (a cloud
# server). UTC is consistent everywhere. The frontend converts
# UTC to the user's local time for display.
#
# WHY timezone-aware?
# Python datetime objects can be "naive" (no timezone info) or
# "aware" (with timezone info). Naive datetimes are ambiguous and
# cause subtle bugs when comparing times or calculating durations.
# We always use aware datetimes: datetime.now(timezone.utc)

from enum import Enum
# Enum: Python's enumeration base class.
# Used to declare the fixed set of valid session statuses.
# Same pattern as InputSource in trigger.py.

from typing import Optional, Dict
# Optional[X]: The value can be X or None.
# Dict[K, V]: A dictionary mapping keys of type K to values of type V.
# Used for the in-memory session store type annotation.

from pydantic import BaseModel, Field
# BaseModel: Foundation for all Privo data models.
# Field: Adds metadata (defaults, descriptions) to model fields.

from app.core.config import settings
# settings: Central configuration singleton.
# We read default values from it to populate DefaultSettings.

from app.core.logging import get_logger
# get_logger: Logging factory from logging.py.

from app.pipeline.intake.trigger import TriggerEngine, PrivoFrame, InputSource
# PrivoFrame: The normalised input container from the Trigger Engine.
#   This is what the Session Manager receives and stores.
# InputSource: The enum of valid input sources (GALLERY, CAMERA, VIDEO).
#   We store this on the session so analytics can report by source type.

logger = get_logger(__name__)
# __name__ = "app.engine.session"
# Logger name = "privo.app.engine.session"


# ─────────────────────────────────────────────────────────────────
# SESSION STATUS ENUM
# Declares the lifecycle stages of a Privo session.
# ─────────────────────────────────────────────────────────────────

class SessionStatus(str, Enum):
    """
    The lifecycle status of a Privo analysis session.

    WHY AN ENUM?
    ------------
    Without an enum, status would be a plain string like "pending".
    A developer could accidentally write "Pending" or "PENDING" or
    "pendng" — Python wouldn't complain, and the bug would be silent.
    With SessionStatus.PENDING, a typo is an AttributeError immediately.

    WHY INHERIT FROM str?
    ----------------------
    Same reason as InputSource: str inheritance means Pydantic
    serialises the value as a plain string in JSON:
        {"status": "pending"}  not  {"status": "SessionStatus.PENDING"}
    This is what the React frontend will receive and display.

    LIFECYCLE TRANSITIONS
    ----------------------
    PENDING     Initial state when session is first created.
                The pipeline has not begun processing yet.
                This is the state returned in Week 1.

    PROCESSING  Set when the Detection Engine begins analysing the frame.
                Future: analyze.py will update status to PROCESSING
                before starting the engine pipeline.

    COMPLETE    Set when all pipeline stages have finished.
                Future: the final stage (Risk Scoring or Heatmap Engine)
                will update status to COMPLETE when results are ready.

    TERMINATED  Set when the session is explicitly closed.
                Future: Session Termination Module sets this on:
                  - User closes the session manually
                  - Session expiry timeout (settings.session_expiry_minutes)
                  - Server shutdown cleanup
    """

    PENDING     = "pending"
    PROCESSING  = "processing"
    COMPLETE    = "complete"
    TERMINATED  = "terminated"


# ─────────────────────────────────────────────────────────────────
# DEFAULT SETTINGS MODEL
# Typed representation of the user's settings for this session.
# Loaded from config.py defaults in Week 1.
# Future: overridden by user preferences from a Settings UI.
# ─────────────────────────────────────────────────────────────────

class DefaultSettings(BaseModel):
    """
    The settings applied to one analysis session.

    WHY A SEPARATE MODEL AND NOT A FLAT DICT?
    ------------------------------------------
    If settings were a plain dict attached to SessionData:
        session.settings["scanning_mode"]
    then every module that reads settings has to know the exact
    key string. A typo ("scaning_mode") causes a KeyError at runtime.

    As a typed Pydantic model:
        session.settings.scanning_mode
    is validated at construction time. IDEs autocomplete it.
    The Detection Engine and Risk Scoring Engine can import
    DefaultSettings and know exactly what fields are available.

    IN WEEK 1
    ---------
    These values come from config.py (hardcoded defaults).
    There is no Settings UI yet — all sessions use the same defaults.

    IN THE FUTURE
    -------------
    When the Settings UI is built, the user's preferences will be
    loaded here instead of the config defaults. The structure of
    DefaultSettings remains unchanged — only the values change.
    This means every engine that reads session.settings works
    correctly without modification when personalised settings arrive.

    FIELDS AND WHAT USES THEM
    --------------------------
    theme             → Frontend only. Backend ignores this.
    scanning_mode     → Risk Scoring Engine: determines check intensity.
    metadata_retention→ Metadata Extractor: whether to include EXIF data.
    analysis_history  → Memory Engine: whether to persist session history.
    cloud_processing  → Detection Engine: whether to use cloud ML models.
    """

    theme: str = Field(
        default=settings.default_theme,
        description="UI theme preference: 'light', 'dark', or 'system'"
    )

    scanning_mode: str = Field(
        default=settings.default_scanning_mode,
        description="Analysis intensity: 'fast', 'balanced', or 'thorough'"
    )

    metadata_retention: bool = Field(
        default=settings.default_metadata_retention,
        description="Whether to include metadata in analysis results"
    )

    analysis_history: bool = Field(
        default=settings.default_analysis_history,
        description="Whether to store this session in analysis history"
    )

    cloud_processing: bool = Field(
        default=settings.default_cloud_processing,
        description="Whether to use cloud AI processing (false = local only)"
    )


# ─────────────────────────────────────────────────────────────────
# SESSION DATA MODEL
# The complete data container for one analysis session.
# Created by SessionManager and passed through the entire pipeline.
# ─────────────────────────────────────────────────────────────────

class SessionData(BaseModel):
    """
    The complete data container for one Privo analysis session.

    This is the object that flows through the entire pipeline after
    the Trigger Engine's validation is complete.

    Every engine in the pipeline receives this object, reads what it
    needs, adds its results, and passes it to the next engine.

    THINK OF IT AS A "WORK ORDER"
    ------------------------------
    When a car enters a repair shop, a work order is created.
    It starts with: customer name, car details, reported problem.
    As mechanics work on it, they add: findings, parts used, labour.
    At the end: invoice, completion time, sign-off.

    SessionData works the same way:
    - Created with: session_id, privo_frame, settings, timestamps
    - Detection Engine adds: detected regions (future)
    - Risk Scoring Engine adds: risk scores (future)
    - Heatmap Engine adds: heatmap data (future)
    - Final Image Builder adds: output path (future)

    FIELDS
    ------
    session_id : str
        Unique identifier. Format: "PRIVO-SESSION-XXXXXXXX"
        where XXXXXXXX is 8 uppercase hex characters.
        Generated by SessionManager._generate_session_id().

    privo_frame : PrivoFrame
        The normalised input from the Trigger Engine.
        Contains the raw image bytes and source metadata.
        This is what the Detection Engine reads for analysis.

    source : InputSource
        Copied from privo_frame.source for convenient top-level access.
        Stored separately so analytics queries don't need to unpack
        the full PrivoFrame to filter by source type.

    settings : DefaultSettings
        The analysis settings for this session.
        Read by: Detection Engine, Risk Scoring Engine, Memory Engine.

    status : SessionStatus
        Current lifecycle stage. Starts as PENDING.
        Updated by each pipeline stage as processing progresses.

    created_at : datetime
        UTC timestamp of session creation.
        Used by Session Termination Module to enforce expiry.
        Used by Analytics Dashboard to report session volume over time.

    updated_at : datetime
        UTC timestamp of the last status update.
        Updated whenever status changes or results are added.
        Useful for detecting stalled sessions (processing for too long).

    settings_loaded : bool
        Confirms that DefaultSettings were successfully loaded.
        The React frontend reads this in Week 1 to confirm the
        pipeline initialised correctly.
    """

    model_config = {"arbitrary_types_allowed": True}
    # Required because PrivoFrame contains bytes (raw binary data).
    # Pydantic needs this flag to allow non-standard field types.

    session_id: str = Field(description="Unique session identifier")

    privo_frame: PrivoFrame = Field(description="Normalised input from Trigger Engine")

    source: InputSource = Field(description="Input source type for this session")

    settings: DefaultSettings = Field(description="Analysis settings for this session")

    status: SessionStatus = Field(
        default=SessionStatus.PENDING,
        description="Current lifecycle status of the session"
    )

    created_at: datetime = Field(description="UTC timestamp of session creation")

    updated_at: datetime = Field(description="UTC timestamp of last update")

    settings_loaded: bool = Field(
        default=True,
        description="Confirms default settings were loaded successfully"
    )


# ─────────────────────────────────────────────────────────────────
# SESSION MANAGER
# Creates, stores, retrieves, and terminates sessions.
# ─────────────────────────────────────────────────────────────────

class SessionManager:
    """
    The Session Manager — creates and manages Privo analysis sessions.

    RESPONSIBILITY
    --------------
    1. Generate unique, unguessable session IDs
    2. Load default settings for the session
    3. Build a SessionData object from a validated PrivoFrame
    4. Store the session in memory
    5. Provide retrieval and termination methods

    STORAGE
    -------
    Sessions are stored in a class-level dictionary:
        SessionManager._store: Dict[str, SessionData]

    WHY CLASS-LEVEL (not instance-level)?
    ---------------------------------------
    If _store were an instance variable (self._store = {}), then
    every time the endpoint created a new SessionManager(), it would
    get a fresh empty store — all previous sessions would be invisible.

    A class-level variable is shared across ALL instances of the class.
    Whether you create one SessionManager or ten, they all read from
    and write to the same _store dictionary.

    This is a simple form of the "Singleton" pattern for storage.

    FUTURE MIGRATION
    ----------------
    When Redis or a database replaces the dict, only these methods
    change: create_session(), get_session(), terminate_session().
    No other file in the project needs to be updated.
    """

    _store: Dict[str, SessionData] = {}
    # Dict[str, SessionData]:
    #   Keys   → session_id strings like "PRIVO-SESSION-A3F8B21C"
    #   Values → SessionData objects
    #
    # This dict lives at the CLASS level, not the instance level.
    # It persists for the lifetime of the running server process.

    def create_session(self, privo_frame: PrivoFrame) -> SessionData:
        """
        Creates a new analysis session from a validated PrivoFrame.

        This is the primary method called by the analyze.py endpoint
        after the Trigger Engine returns a successful ValidationResult.

        PARAMETERS
        ----------
        privo_frame : PrivoFrame
            The validated, normalised input from the Trigger Engine.
            Must have already passed all Trigger Engine checks.
            This is the single source of truth for the session's input.

        RETURNS
        -------
        SessionData
            A fully populated session object, already stored in memory.
            The endpoint serialises this to build the JSON response.

        WHAT HAPPENS INSIDE
        --------------------
        1. Generate a unique session ID
        2. Load default settings from config.py
        3. Record the current UTC time as both created_at and updated_at
        4. Build the SessionData object
        5. Store it in _store
        6. Return it

        USAGE IN analyze.py
        --------------------
        manager = SessionManager()
        session = manager.create_session(result.privo_frame)
        return {"session_id": session.session_id, "status": session.status}
        """
        session_id = self._generate_session_id()

        now = datetime.now(timezone.utc)
        # datetime.now(timezone.utc): current time in UTC.
        # We pass timezone.utc explicitly to get a timezone-aware object.
        # This is important: naive datetimes (without timezone) cause
        # subtle bugs when comparing across environments.

        session_settings = DefaultSettings()
        # DefaultSettings() with no arguments uses all the Field defaults,
        # which are populated from the config.py settings object.
        # Example: scanning_mode=settings.default_scanning_mode → "balanced"

        session = SessionData(
            session_id=session_id,
            privo_frame=privo_frame,
            source=privo_frame.source,
            # Copy source to top level for convenient access.
            # Without this, a query like "how many CAMERA sessions today?"
            # would need to unpack every PrivoFrame to check .source.
            # At the top level, it's a direct field lookup.
            settings=session_settings,
            status=SessionStatus.PENDING,
            created_at=now,
            updated_at=now,
            # Both timestamps are identical at creation.
            # updated_at will advance each time the status changes.
            settings_loaded=True
        )

        SessionManager._store[session_id] = session
        # Store using the class name (_store), not self._store.
        # Both work, but using the class name makes it explicit
        # that we are writing to the shared class-level store,
        # not an instance-level variable.

        logger.info(
            f"Session Manager: session created | "
            f"id={session_id} | "
            f"source={privo_frame.source.value} | "
            f"file='{privo_frame.filename}' | "
            f"size={privo_frame.size_bytes} bytes | "
            f"mode={session_settings.scanning_mode}"
        )

        return session

    def get_session(self, session_id: str) -> Optional[SessionData]:
        """
        Retrieves a session by its ID.

        Used by all downstream pipeline engines to access session data.

        PARAMETERS
        ----------
        session_id : str
            The full session ID, e.g. "PRIVO-SESSION-A3F8B21C"

        RETURNS
        -------
        SessionData  → if the session exists in memory
        None         → if the session does not exist or was terminated

        WHY RETURN None INSTEAD OF RAISING AN EXCEPTION?
        -------------------------------------------------
        The caller (an endpoint or engine) needs to decide what to do
        when a session is not found. Returning None gives the caller
        that choice. If we raised an exception here, every caller would
        need a try/except block — more verbose and less flexible.

        The endpoint will check:
            session = manager.get_session(session_id)
            if session is None:
                raise HTTPException(404, "Session not found")

        USAGE IN FUTURE ENDPOINTS
        -------------------------
        GET /api/v1/session/{session_id}/status
            session = manager.get_session(session_id)
            if session is None:
                raise HTTPException(404, "Session not found or expired")
            return {"status": session.status}
        """
        session = SessionManager._store.get(session_id)
        # dict.get(key) returns the value if the key exists,
        # or None if it doesn't — no KeyError raised.
        # This is safer than SessionManager._store[session_id]
        # which would raise KeyError for missing keys.

        if session is None:
            logger.warning(f"Session Manager: session not found — '{session_id}'")
        else:
            logger.debug(f"Session Manager: session retrieved — '{session_id}'")

        return session

    def terminate_session(self, session_id: str) -> bool:
        """
        Marks a session as TERMINATED and removes it from memory.

        Called by the Session Termination Module (future) when:
        - The user explicitly closes the session
        - The session exceeds settings.session_expiry_minutes
        - The server is shutting down and needs to clean up

        PARAMETERS
        ----------
        session_id : str
            The full session ID to terminate.

        RETURNS
        -------
        True  → session was found and terminated successfully
        False → session was not found (already terminated or never existed)

        WHY RETURN bool INSTEAD OF RAISING AN EXCEPTION?
        -------------------------------------------------
        Terminating a non-existent session is not necessarily an error.
        It could mean the session already expired, or a duplicate
        termination request was sent. Returning False lets the caller
        decide whether this is a problem worth logging or alerting on.

        WHAT HAPPENS ON TERMINATION
        ----------------------------
        In Week 1: session is simply deleted from _store.
        Future Memory Engine: before deleting, check if analysis_history
        is True in session.settings. If so, persist the session to
        long-term storage (database or file) before removing from memory.
        """
        session = SessionManager._store.get(session_id)

        if session is None:
            logger.warning(
                f"Session Manager: terminate called for unknown session — '{session_id}'"
            )
            return False

        # Update status before removing from store.
        # Future: Memory Engine checks this status before persisting.
        session.status = SessionStatus.TERMINATED
        session.updated_at = datetime.now(timezone.utc)

        del SessionManager._store[session_id]
        # del: Python's keyword to delete a dictionary entry.
        # The SessionData object is removed from the store.
        # Python's garbage collector will free the memory once no
        # other variables hold a reference to it.

        logger.info(f"Session Manager: session terminated — '{session_id}'")
        return True

    def get_active_session_count(self) -> int:
        """
        Returns the number of sessions currently in memory.

        Used for health monitoring and development debugging.

        Future: The Analytics Dashboard will call this to display
        "Active Sessions" in the admin panel.
        The Session Termination Module will call this to decide
        whether to run an expiry sweep.

        USAGE IN HEALTH ENDPOINT (future)
        ----------------------------------
        GET /api/v1/health
            manager = SessionManager()
            return {
                "status": "healthy",
                "active_sessions": manager.get_active_session_count()
            }
        """
        count = len(SessionManager._store)
        logger.debug(f"Session Manager: active session count — {count}")
        return count

    # ── PRIVATE METHODS ───────────────────────────────────────────

    def _generate_session_id(self) -> str:
        """
        Generates a unique, cryptographically secure session ID.

        FORMAT: "PRIVO-SESSION-XXXXXXXX"
        Where XXXXXXXX is 8 uppercase hexadecimal characters.

        EXAMPLES
        --------
        PRIVO-SESSION-A3F8B21C
        PRIVO-SESSION-0D4E9F7A
        PRIVO-SESSION-C2187B3D

        WHY secrets.token_hex(4)?
        --------------------------
        secrets.token_hex(n) generates n random bytes and returns them
        as a hex string of length 2n.
        token_hex(4) → 4 bytes → 8 hex characters.

        4 bytes = 32 bits of randomness = 4,294,967,296 possible values.
        The chance of a collision (two sessions getting the same ID)
        is negligible for Privo's scale.

        WHY .upper()?
        -------------
        token_hex returns lowercase hex: "a3f8b21c"
        We uppercase it: "A3F8B21C"
        This matches the format shown in the project specification
        and is more readable in log files.

        WHY THE COLLISION CHECK LOOP?
        --------------------------------
        In theory, two calls to token_hex(4) could produce the same value.
        With 4 billion possibilities, this is extremely unlikely, but
        "extremely unlikely" is not "impossible". The loop regenerates
        the token if — by some cosmic coincidence — it already exists.
        This guarantees uniqueness without using a database sequence.
        """
        while True:
            # Generate a candidate ID
            token = secrets.token_hex(4).upper()
            session_id = f"{settings.session_prefix}-{token}"
            # settings.session_prefix = "PRIVO-SESSION" (from config.py)
            # token = "A3F8B21C" (example)
            # result = "PRIVO-SESSION-A3F8B21C"

            if session_id not in SessionManager._store:
                # This ID doesn't exist yet — safe to use.
                logger.debug(f"Session Manager: generated session ID — '{session_id}'")
                return session_id
            # If it already exists (extraordinarily unlikely),
            # the loop continues and generates a new candidate.
            logger.warning(
                f"Session Manager: session ID collision detected — "
                f"'{session_id}' already exists. Regenerating."
            )
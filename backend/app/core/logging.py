"""
backend/app/core/logging.py

PURPOSE
-------
This file sets up Privo's logging system.

Every module in the backend will import `get_logger` from here
and use it to report what it is doing, what errors occurred,
and what warnings should be noted.

WHY THIS FILE EXISTS
--------------------
Without a central logging setup, each module would need to
configure logging on its own — or worse, use print() everywhere.

A single logging setup means:
- Consistent format across all modules
- One place to change log level (e.g. turn off DEBUG in production)
- One place to add file logging, cloud logging, or JSON logging later

HOW OTHER MODULES USE THIS FILE
---------------------------------
Every module that wants to log something does this:

    from app.core.logging import get_logger
    logger = get_logger(__name__)

    # Then:
    logger.debug("Very detailed message only useful in dev")
    logger.info("Normal operation message")
    logger.warning("Something unexpected but not fatal")
    logger.error("Something went wrong")

The __name__ argument is Python's built-in variable that holds
the module's full name, like "app.engine.trigger" or "app.engine.session".
This appears in the log output so you always know which module logged it.

FUTURE MODULES THAT WILL DEPEND ON THIS FILE
---------------------------------------------
Every single Privo module:
- trigger.py
- session.py
- analyze.py
- main.py
- metadata_extractor (Week 2)
- detection_engine (Week 3)
- risk_scoring_engine (Week 4)
- privacy_heatmap_engine (Week 5)
- All future engines
"""

import logging
# logging: Python's built-in logging module.
# Provides Logger objects, log levels (DEBUG/INFO/WARNING/ERROR/CRITICAL),
# Handlers (where to send logs), and Formatters (how to format them).
# No installation needed — it's part of Python's standard library.

import sys
# sys: Python's system module.
# We use sys.stdout here to send log output to the terminal.
# This is standard for web applications — process managers like
# Docker or systemd capture stdout and store it as the app log.

from typing import Optional
# Optional: A type hint meaning "this can be either the type or None".
# Used below for the optional log level parameter.


# ─────────────────────────────────────────────
# LOG FORMAT
# This string defines how every log line will look.
# ─────────────────────────────────────────────

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
# %(asctime)s   → Timestamp: "2025-01-15 14:23:01,456"
# %(levelname)s → Level: "INFO", "DEBUG", "WARNING", "ERROR"
# -8s           → Pad to 8 characters so columns align nicely
# %(name)s      → Module name: "app.engine.trigger"
# %(message)s   → The actual log message

# EXAMPLE OUTPUT:
# 2025-01-15 14:23:01,456 | INFO     | app.engine.trigger | File validated successfully
# 2025-01-15 14:23:01,460 | INFO     | app.engine.session | Session created: PRIVO-SESSION-A3F8B21C
# 2025-01-15 14:23:02,001 | ERROR    | app.engine.trigger | File too large: 45.2 MB

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
# The format for the timestamp part of the log.
# %Y = 4-digit year, %m = month, %d = day
# %H = 24h hour, %M = minute, %S = second


# ─────────────────────────────────────────────
# ROOT LOGGER NAME
# All Privo loggers will be children of this root.
# ─────────────────────────────────────────────

PRIVO_ROOT_LOGGER = "privo"
# Python's logging system is hierarchical.
# A logger named "privo.engine.trigger" is a child of "privo.engine",
# which is a child of "privo".
# Settings applied to the parent automatically apply to all children.
# This means: configure "privo" once → all modules get the same setup.


def setup_logging(log_level: Optional[str] = None) -> None:
    """
    WHAT THIS FUNCTION DOES
    -----------------------
    Configures the entire Privo logging system.
    This function must be called ONCE at startup (in main.py).

    After it runs, every call to get_logger() anywhere in the app
    will produce correctly formatted, levelled log output.

    PARAMETERS
    ----------
    log_level : Optional[str]
        The minimum severity level to log.
        If None, defaults to "DEBUG" (log everything).

        Examples:
        - "DEBUG"   → log everything (use in development)
        - "INFO"    → log info, warnings, and errors (use in staging)
        - "WARNING" → log only warnings and errors (use in production)
        - "ERROR"   → log only errors (very quiet production)

    WHY THIS FUNCTION MUST BE CALLED BEFORE ANYTHING ELSE
    -------------------------------------------------------
    Python's logging system works even without setup (it uses
    a default handler that may not format nicely). By calling
    setup_logging() first in main.py, we guarantee every log
    message looks the way we want from the very first line.

    HOW main.py WILL CALL THIS
    ---------------------------
    from app.core.logging import setup_logging
    setup_logging(log_level="DEBUG")  # during development
    """

    # Resolve which log level to use
    level_str: str = log_level or "DEBUG"
    # If log_level was not passed, default to DEBUG.
    # DEBUG is most verbose — ideal for development where you want
    # to see everything happening inside the engine.

    # Convert the string level name to Python's numeric constant
    numeric_level: int = getattr(logging, level_str.upper(), logging.DEBUG)
    # getattr(logging, "DEBUG") → returns logging.DEBUG (which equals 10)
    # getattr(logging, "INFO")  → returns logging.INFO  (which equals 20)
    # getattr(logging, "INVALID", logging.DEBUG) → returns logging.DEBUG
    # The third argument is the fallback if the name doesn't exist.
    # This protects against typos in log level configuration.

    # ─────────────────────────────────────────────
    # CREATE THE FORMATTER
    # A Formatter controls how each log line looks.
    # ─────────────────────────────────────────────
    formatter = logging.Formatter(
        fmt=LOG_FORMAT,
        datefmt=DATE_FORMAT
    )
    # fmt     → The message format string defined above
    # datefmt → The date/time format string defined above

    # ─────────────────────────────────────────────
    # CREATE THE HANDLER
    # A Handler decides WHERE log messages go.
    # Week 1: Console only (terminal output).
    # Future: Add FileHandler to write to a log file.
    #         Add rotating handlers to prevent files from growing forever.
    # ─────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    # StreamHandler: Sends log messages to a stream (a writable channel).
    # sys.stdout: The terminal output stream.
    # This means all logs appear in the terminal when you run the app.

    console_handler.setFormatter(formatter)
    # Attach our formatter to this handler.
    # Without this, the handler would use Python's default format,
    # which is just the message with no timestamp or module name.

    console_handler.setLevel(numeric_level)
    # The handler also has a level filter.
    # Messages below this level are ignored by this handler.
    # Both the logger AND the handler check the level.
    # A message must pass BOTH checks to appear in the output.

    # ─────────────────────────────────────────────
    # CONFIGURE THE ROOT PRIVO LOGGER
    # This is the parent of all module-specific loggers.
    # ─────────────────────────────────────────────
    root_logger = logging.getLogger(PRIVO_ROOT_LOGGER)
    # getLogger("privo"): Gets (or creates) a logger named "privo".
    # All child loggers like "privo.engine.trigger" will inherit
    # this logger's settings automatically.

    root_logger.setLevel(numeric_level)
    # Set the minimum level for the root Privo logger.
    # Messages below this level will be ignored before
    # they even reach a handler.

    # Avoid duplicate handlers if setup_logging is called more than once
    if not root_logger.handlers:
        # root_logger.handlers: A list of handlers already attached.
        # If it's empty, no handlers have been attached yet → safe to add.
        # This guard prevents duplicate log lines if the function
        # is accidentally called twice (which can happen in some
        # FastAPI reload scenarios during development).
        root_logger.addHandler(console_handler)

    # ─────────────────────────────────────────────
    # SUPPRESS NOISY THIRD-PARTY LOGGERS
    # Some libraries log too much detail that clutters your output.
    # We silence them or raise their minimum level.
    # ─────────────────────────────────────────────
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    # uvicorn.access: Uvicorn logs every HTTP request by default.
    # Example: "GET /api/v1/analyze HTTP/1.1 200"
    # This floods your terminal during development.
    # Setting it to WARNING means it only appears for warnings/errors,
    # not for every normal request.
    # You can comment this line out if you want to see all HTTP requests.

    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    # uvicorn.error: Uvicorn's error logger.
    # We keep this at INFO so startup messages ("Uvicorn running on...")
    # are visible, which is useful feedback during development.

    logging.getLogger("multipart").setLevel(logging.WARNING)
    # multipart: The library that handles multipart/form-data file uploads.
    # It can log very detailed parsing information we don't need.

    # Log confirmation that setup is complete
    logger = logging.getLogger(PRIVO_ROOT_LOGGER)
    logger.info("Privo logging system initialised")
    # This is the first log message Privo will ever produce.
    # If you see this line in your terminal, logging is working correctly.


def get_logger(name: str) -> logging.Logger:
    """
    WHAT THIS FUNCTION DOES
    -----------------------
    Returns a Logger object for the calling module.

    This is the ONE function that every other module will call.
    It's a simple wrapper around Python's logging.getLogger(),
    but it namespaces all loggers under "privo." automatically.

    PARAMETERS
    ----------
    name : str
        Usually the module's __name__ variable.

        When trigger.py calls get_logger(__name__), Python passes
        "app.engine.trigger" as the name.

        We prefix it with "privo." to make: "privo.app.engine.trigger"

        This ensures all Privo loggers are children of the root
        "privo" logger we configured in setup_logging().

    RETURNS
    -------
    logging.Logger
        A Logger object with .debug(), .info(), .warning(),
        .error(), and .critical() methods.

    USAGE IN EVERY MODULE
    ----------------------
    from app.core.logging import get_logger

    logger = get_logger(__name__)

    # Then use anywhere in the module:
    logger.debug("Detailed internal message")
    logger.info("Session PRIVO-SESSION-A3F8B21C created")
    logger.warning("File size approaching limit: 18.5 MB")
    logger.error("Unsupported file extension: .bmp")

    EXTRA CONTEXT (BEST PRACTICE)
    ------------------------------
    You can attach extra data to any log message using the `extra` dict:

    logger.info("Session created", extra={"session_id": session_id})

    In Week 1, we keep it simple and just use f-strings in the message.
    Future weeks may adopt structured logging (like structlog library)
    where extra data is attached as structured fields.

    WHY NOT JUST CALL logging.getLogger() DIRECTLY?
    ------------------------------------------------
    You could. But then every module has to remember to prefix with
    "privo." themselves. Having one central get_logger() function
    means the prefix is automatic and consistent everywhere.
    """
    namespaced_name = f"{PRIVO_ROOT_LOGGER}.{name}"
    # Example transformations:
    # "app.engine.trigger" → "privo.app.engine.trigger"
    # "app.engine.session" → "privo.app.engine.session"
    # "app.api.v1.endpoints.analyze" → "privo.app.api.v1.endpoints.analyze"

    return logging.getLogger(namespaced_name)
    # logging.getLogger(): Gets the logger with this name.
    # If it doesn't exist, Python creates it automatically.
    # If it already exists (e.g. called twice), Python returns
    # the same instance — loggers are cached by name.
    # This is safe to call many times — it's always the same object.
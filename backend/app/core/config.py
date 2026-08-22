"""
backend/app/core/config.py

PURPOSE
-------
This is the central configuration file for the entire Privo backend.
Think of it as the "settings panel" for the whole application.

Every configurable value lives here in one place.
No module should ever have a hardcoded number or string that
might need to change in the future — those belong here.

WHY THIS FILE EXISTS
--------------------
Without a config file, you end up with values scattered across
every file. When you need to change the max upload size, you'd
have to search every file. With config.py, you change it once.

HOW IT COMMUNICATES WITH OTHER MODULES
----------------------------------------
Every module that needs a setting will import `settings` from here:

    from app.core.config import settings

    # Then use it like this:
    if file_size > settings.max_file_size_bytes:
        raise error

FUTURE MODULES THAT WILL DEPEND ON THIS FILE
---------------------------------------------
- trigger.py          → reads MAX_FILE_SIZE_MB, ALLOWED_EXTENSIONS
- session.py          → reads SESSION_PREFIX, SESSION_EXPIRY_MINUTES
- analyze.py          → reads DEFAULT_SETTINGS block
- metadata_extractor  → reads METADATA_RETENTION from default settings
- risk_scoring_engine → will read risk thresholds added here later
- memory_engine       → will read session expiry / history settings
- Every future module → because everything is configured from here
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
# pydantic_settings: A Pydantic extension that reads values from
# environment variables or .env files automatically.
# Install: pip install pydantic-settings

from pydantic import Field
# Field: Used to give extra metadata to Pydantic model fields,
# like default values and documentation strings.

from typing import List
# List: Python's type hint for a list of items.
# Used here to define a list of allowed file extensions.


class Settings(BaseSettings):
    """
    Settings class — holds all Privo configuration values.

    WHY USE A CLASS?
    ----------------
    A class lets us group all settings together and access them
    like attributes: settings.app_name, settings.max_file_size_mb

    WHY INHERIT FROM BaseSettings?
    --------------------------------
    BaseSettings (from pydantic_settings) does two powerful things:
    1. Reads values from environment variables automatically.
       So if you set APP_NAME=Privo in your .env file, it reads that.
    2. Validates types. If MAX_FILE_SIZE_MB should be an int but you
       put "hello" in .env, Pydantic raises a clear error immediately.

    HOW ENVIRONMENT LOADING WORKS
    ------------------------------
    If the environment variable exists → use it.
    If it doesn't → use the default value defined below.

    This means your defaults work out of the box for development,
    and you can override them in production with environment variables.
    """

    model_config = SettingsConfigDict(
        # model_config: Tells Pydantic how to behave.
        # SettingsConfigDict is a typed way to configure BaseSettings.

        env_file=".env",
        # env_file: Which file to read environment variables from.
        # .env is the standard convention (the file in your backend/ folder).
        # In production, you'd use real environment variables instead.

        env_file_encoding="utf-8",
        # env_file_encoding: How to read the .env file.
        # UTF-8 is standard and supports special characters.

        case_sensitive=False,
        # case_sensitive=False: Environment variable names are not
        # case sensitive. APP_NAME and app_name both work.
    )

    # ─────────────────────────────────────────────
    # APP IDENTITY
    # These values describe the application itself.
    # ─────────────────────────────────────────────

    app_name: str = Field(default="Privo", description="Name of the application")
    # str: This must be a text string.
    # Field(default=...): The value to use if not set in environment.

    app_version: str = Field(default="0.1.0", description="Current version")
    # Semantic versioning: major.minor.patch
    # 0.1.0 means: early development, first minor version, no patches.

    app_description: str = Field(
        default="Privacy Intelligence Assistant",
        description="Short description of Privo"
    )

    debug: bool = Field(default=True, description="Enable debug mode")
    # bool: True or False.
    # debug=True in development → enables extra logging, error details.
    # debug=False in production → hides internal error details from users.

    # ─────────────────────────────────────────────
    # API CONFIGURATION
    # These values control how the API behaves.
    # ─────────────────────────────────────────────

    api_v1_prefix: str = Field(default="/api/v1", description="API version prefix")
    # All routes will start with /api/v1
    # Example: /api/v1/analyze
    # This prefix makes it easy to add /api/v2 in the future without
    # breaking existing clients using /api/v1.

    allowed_origins: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="Allowed CORS origins"
    )
    # CORS (Cross-Origin Resource Sharing):
    # When your React app at localhost:5173 calls your FastAPI at localhost:8000,
    # the browser blocks the request by default (they're different "origins").
    # CORS tells the browser: "it's okay, these origins are trusted."
    # localhost:5173 is Vite's default dev port.
    # localhost:3000 is Create React App's default dev port.

    # ─────────────────────────────────────────────
    # FILE VALIDATION SETTINGS
    # These values are used by the Trigger Engine to validate uploads.
    # ─────────────────────────────────────────────

    max_file_size_mb: int = Field(default=20, description="Maximum upload size in megabytes")
    # int: Whole number, no decimals.
    # 20 MB is a reasonable limit for photos from phone cameras.

    allowed_extensions: List[str] = Field(
        default=["jpg", "jpeg", "png", "webp", "heic", "heif"],
        description="Supported image file extensions"
    )
    # These are the extensions Privo can accept.
    # Note: no dots. We strip dots when comparing extensions.
    # jpg/jpeg: Most common photo format.
    # png: Lossless format, common for screenshots.
    # webp: Modern efficient format used by many phones and browsers.
    # heic/heif: iPhone's native format (High Efficiency Image Format).

    @property
    def max_file_size_bytes(self) -> int:
        """
        WHAT IS A @property?
        A property is a method that behaves like an attribute.
        Instead of calling settings.max_file_size_bytes(),
        you call it like settings.max_file_size_bytes (no parentheses).

        WHY THIS PROPERTY EXISTS
        The Trigger Engine needs bytes for comparison with actual file sizes.
        Storing MB in config and converting here keeps config human-readable.

        EXAMPLE USAGE IN TRIGGER ENGINE
        if upload.size > settings.max_file_size_bytes:
            raise error
        """
        return self.max_file_size_mb * 1024 * 1024
        # 1 MB = 1024 KB = 1024 * 1024 bytes = 1,048,576 bytes

    # ─────────────────────────────────────────────
    # SESSION CONFIGURATION
    # These values control how sessions are created and stored.
    # Used by: Session Manager
    # ─────────────────────────────────────────────

    session_prefix: str = Field(default="PRIVO-SESSION", description="Prefix for session IDs")
    # All Privo session IDs will look like: PRIVO-SESSION-A3F8B21C
    # The prefix makes them easy to identify in logs.

    session_expiry_minutes: int = Field(default=60, description="Session lifetime in minutes")
    # Sessions are stored in memory. After 60 minutes, a session expires.
    # Future: Memory Engine will use this to clean up old sessions.

    # ─────────────────────────────────────────────
    # DEFAULT USER SETTINGS
    # These are the settings applied to every new session.
    # In the future, users will be able to change these in a Settings UI.
    # For Week 1, they are hardcoded here.
    #
    # Future modules that will use these:
    # - Metadata Extractor → reads metadata_retention
    # - Memory Engine → reads analysis_history
    # - Detection Engine → reads scanning_mode
    # ─────────────────────────────────────────────

    default_theme: str = Field(
        default="system",
        description="UI theme: 'light', 'dark', or 'system'"
    )
    # 'system' means: follow the operating system's dark/light mode setting.

    default_scanning_mode: str = Field(
        default="balanced",
        description="Scanning intensity: 'fast', 'balanced', or 'thorough'"
    )
    # fast: Fewer checks, quicker results. Good for previewing.
    # balanced: Moderate checks. Good for everyday use.
    # thorough: All checks enabled. Slower but most comprehensive.

    default_metadata_retention: bool = Field(
        default=True,
        description="Whether to include metadata in analysis results"
    )
    # True: Metadata is shown to the user in the analysis results.
    # False: Metadata is stripped from the display.

    default_analysis_history: bool = Field(
        default=True,
        description="Whether to keep analysis history in the session"
    )
    # True: User can see previous analyses during a session.
    # False: Each analysis is standalone with no history.

    default_cloud_processing: bool = Field(
        default=False,
        description="Whether to use cloud AI processing"
    )
    # False by default for privacy: everything runs locally.
    # Future: When cloud ML models are integrated, this toggles them.


def get_settings() -> Settings:
    """
    WHAT IS THIS FUNCTION?
    A factory function that creates and returns the Settings object.

    WHY NOT JUST IMPORT Settings DIRECTLY?
    ----------------------------------------
    Using a function (rather than a module-level instance) makes it
    easier to override settings in tests. In your test file, you can
    replace get_settings() with a function that returns test-specific
    settings, without affecting the real config.

    HOW IT WILL BE USED
    ---------------------
    Option A — Simple import (good for Week 1):
        from app.core.config import settings

    Option B — Dependency injection in FastAPI (future):
        from fastapi import Depends
        from app.core.config import get_settings
        def my_endpoint(settings = Depends(get_settings)):
            ...

    WHY DEPENDENCY INJECTION?
    FastAPI's Depends() system lets you swap settings in tests easily.
    Week 1 uses the simple import. Week 2+ may move to Depends().
    """
    return Settings()


# Module-level instance.
# This is created ONCE when Python first imports this file.
# Every module that does `from app.core.config import settings`
# gets this same object — they all share one Settings instance.
# This is called the "Singleton" pattern (one shared instance).
settings: Settings = get_settings()
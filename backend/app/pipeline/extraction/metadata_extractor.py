"""
app/pipeline/extraction/metadata_extractor.py

PURPOSE
-------
The Metadata Extractor reads all metadata embedded in an image file
using ExifTool and returns it as a structured Python object.

This is the first engine in Privo's extraction stage. It operates
on the raw bytes inside PrivoFrame — before any pixel-level analysis.

─────────────────────────────────────────────────────────────────────
WHAT IS IMAGE METADATA?
─────────────────────────────────────────────────────────────────────
When a phone or camera takes a photo, it embeds invisible data
alongside the visible pixels. This data is called EXIF metadata
(Exchangeable Image File Format). It can include:

    GPS coordinates    → exactly where the photo was taken
    Device make/model  → "Apple iPhone 15 Pro"
    Timestamp          → exact date and time
    Software version   → iOS 17.2, Instagram 300.0
    Orientation        → portrait or landscape
    Exposure settings  → aperture, shutter speed, ISO
    Lens information   → focal length, lens model

When an image is shared online, this metadata travels with the file
unless it is explicitly removed. This is Privo's primary concern:
most users do not know this data exists, let alone that it is shared.

─────────────────────────────────────────────────────────────────────
WHY EXIFTOOL?
─────────────────────────────────────────────────────────────────────
ExifTool (by Phil Harvey) is the industry standard for reading and
writing image metadata. It supports over 30,000 unique metadata tags
across hundreds of file formats. No Python library comes close to
its breadth and accuracy.

ExifTool is a Perl program — not a Python library.
Python calls it as an external subprocess:
    1. Write image bytes to a temporary file
    2. Run: exiftool -j -n <temp_file_path>
       -j  → output as JSON
       -n  → numeric values (not human-readable converted strings)
    3. Read ExifTool's stdout
    4. Parse the JSON output
    5. Delete the temp file

─────────────────────────────────────────────────────────────────────
WHY -n (NUMERIC VALUES)?
─────────────────────────────────────────────────────────────────────
Without -n, ExifTool converts many fields to human-readable strings:
    GPSLatitude:  "37 deg 46' 30.00\" N"
    ExposureTime: "1/1000"
    FocalLength:  "26.0 mm"
    Flash:        "Auto, Did not fire"

With -n, ExifTool returns the raw numeric values:
    GPSLatitude:  37.775       (float — directly usable for mapping)
    ExposureTime: 0.001        (float — directly usable for math)
    FocalLength:  26.0         (float — directly usable)
    Flash:        24           (int bitmask — decoded by MetadataVault)

Numeric values are unambiguous and do not require string parsing.
MetadataVault reasons about numbers, not formatted strings.

─────────────────────────────────────────────────────────────────────
WHY A TEMP FILE INSTEAD OF STDIN PIPE?
─────────────────────────────────────────────────────────────────────
ExifTool is designed to work with file paths, not stdin streams.
While ExifTool does support reading from stdin (-), the output is
less reliable across all format types. Writing to a NamedTemporaryFile
is the correct, well-tested pattern for programmatic ExifTool usage.

NamedTemporaryFile with delete=False:
    - Creates the file, we write to it, close it
    - ExifTool reads it by path
    - We manually delete it in a finally block
    This guarantees cleanup even if ExifTool crashes.

─────────────────────────────────────────────────────────────────────
HOW THIS FILE COMMUNICATES WITH OTHER MODULES
─────────────────────────────────────────────────────────────────────
Receives from:
    app/pipeline/intake/trigger.py
        → PrivoFrame (contains .content bytes and .source)

Produces:
    RawMetadata → passed to MetadataVault for classification

Called by:
    app/api/v1/endpoints/analyze.py
        → after SessionManager.create_session()
        → before MetadataVault.classify()

Logs via:
    app/core/logging.py

FUTURE MODULES THAT WILL DEPEND ON THIS FILE
---------------------------------------------
- MetadataVault         → classifies the raw output from this file
- Risk Scoring Engine   → uses classified findings to score exposure
- Detection Engine      → uses GPS/timestamp context to guide detection
"""

import json
import subprocess
import tempfile
import os

from typing import Optional, Dict, Any
# Dict[str, Any]: ExifTool outputs many different field types
# (str, int, float, nested structures). Any is correct here —
# the type of each field depends on the tag. MetadataVault handles
# type-specific reasoning after extraction is complete.

from pydantic import BaseModel, Field
from app.core.logging import get_logger

# UPDATED IMPORT PATH (app.engine.trigger in Week 1 → app.pipeline.intake.trigger)
from app.pipeline.intake.trigger import PrivoFrame

logger = get_logger(__name__)
# __name__ = "app.pipeline.extraction.metadata_extractor"
# Logger name = "privo.app.pipeline.extraction.metadata_extractor"


# ─────────────────────────────────────────────────────────────────
# RAW METADATA MODEL
# The structured output of the Metadata Extractor.
# Passed to MetadataVault for classification.
# ─────────────────────────────────────────────────────────────────

class RawMetadata(BaseModel):
    """
    The complete raw metadata output from ExifTool for one image.

    WHY A PYDANTIC MODEL INSTEAD OF A PLAIN DICT?
    -----------------------------------------------
    MetadataVault receives this object and reads specific fields
    by name: raw.gps_latitude, raw.device_make, etc.
    A typed model means:
    - Field names are guaranteed — no KeyError on missing fields
    - All fields default to None — missing metadata is safe to access
    - IDE autocomplete works — MetadataVault authors see all fields
    - Adding a new field here makes it available to MetadataVault
      without any other changes

    FIELD SELECTION RATIONALE
    --------------------------
    These fields were chosen because they carry privacy signals that
    contribute to Privo's exposure analysis. Metadata can provide
    evidence for a subset of Privo's official exposure categories:

        Location Exposure  → GPS coordinates (latitude, longitude, altitude)
        Identity Exposure  → device make/model, author and annotation fields
        Activity Exposure  → capture timestamps, flash, software used
        Contact Exposure   → artist, copyright, XPAuthor fields
        Travel Exposure    → GPS combined with timestamp context

    Metadata extraction cannot provide evidence for exposure categories
    that require pixel-level analysis (Child Safety, Workplace, Financial,
    Document, Educational). Those categories are served by the Detection
    Engine in pipeline/detection/, which operates on image pixels directly.

    The full ExifTool output (all fields) is stored in `all_fields`
    for completeness and future use. MetadataVault reads the named
    fields for its classification logic. Future engines that need
    fields not yet in EXIFTOOL_FIELD_MAP can read from all_fields
    without requiring a second ExifTool subprocess call.

    TYPE NOTES (all fields use ExifTool -j -n output types)
    --------------------------------------------------------
    GPS fields:        float (decimal degrees, already converted by -n)
    Ref fields:        str   ("N", "S", "E", "W")
    Timestamp fields:  str   (ExifTool format: "YYYY:MM:DD HH:MM:SS")
    Device fields:     str
    ExposureTime:      float (seconds: 0.001 = 1/1000s, 0.016 = 1/60s)
    FNumber:           float (e.g. 1.8, 2.8, 4.0)
    ISO:               int
    FocalLength:       float (millimetres: 26.0, 77.0, 4.2)
    Flash:             int   (EXIF bitmask: 0=no flash, 1=fired, 24=auto/off)
    WhiteBalance:      int   (0=auto, 1=manual)
    Orientation:       int   (EXIF spec 1–8: 1=normal, 3=180°, 6=90°CW, 8=90°CCW)
    FileSize:          int   (bytes)
    """

    # ── GPS ───────────────────────────────────────────────────────
    gps_latitude: Optional[float] = Field(default=None)
    gps_longitude: Optional[float] = Field(default=None)
    gps_altitude: Optional[float] = Field(default=None)
    gps_latitude_ref: Optional[str] = Field(default=None)
    gps_longitude_ref: Optional[str] = Field(default=None)
    gps_date_stamp: Optional[str] = Field(default=None)
    gps_time_stamp: Optional[str] = Field(default=None)

    # ── DEVICE ────────────────────────────────────────────────────
    device_make: Optional[str] = Field(default=None)
    device_model: Optional[str] = Field(default=None)
    device_software: Optional[str] = Field(default=None)
    lens_make: Optional[str] = Field(default=None)
    lens_model: Optional[str] = Field(default=None)

    # ── TIMESTAMPS ────────────────────────────────────────────────
    datetime_original: Optional[str] = Field(default=None)
    datetime_digitized: Optional[str] = Field(default=None)
    create_date: Optional[str] = Field(default=None)
    modify_date: Optional[str] = Field(default=None)

    # ── CONTENT / ANNOTATIONS ─────────────────────────────────────
    image_description: Optional[str] = Field(default=None)
    user_comment: Optional[str] = Field(default=None)
    artist: Optional[str] = Field(default=None)
    copyright: Optional[str] = Field(default=None)
    xp_comment: Optional[str] = Field(default=None)
    xp_author: Optional[str] = Field(default=None)
    xp_subject: Optional[str] = Field(default=None)
    xp_keywords: Optional[str] = Field(default=None)

    # ── FILE INFO ─────────────────────────────────────────────────
    file_name: Optional[str] = Field(default=None)
    file_size: Optional[int] = Field(default=None)
    file_type: Optional[str] = Field(default=None)
    mime_type: Optional[str] = Field(default=None)

    # ── CAMERA SETTINGS ───────────────────────────────────────────
    # FIX 1: All five fields below corrected to their actual ExifTool -n types.
    # Previous declarations were Optional[str] which caused Pydantic to
    # silently coerce numeric values to strings, losing type usability.

    exposure_time: Optional[float] = Field(default=None)
    # ExifTool -n: float in seconds. 0.001 = 1/1000s. 0.016 = 1/60s.
    # Without -n it would be "1/1000" (str requiring parsing).

    f_number: Optional[float] = Field(default=None)
    # ExifTool -n: float. 1.8, 2.8, 4.0. Unchanged — was already float.

    iso: Optional[int] = Field(default=None)
    # ExifTool -n: int. 100, 400, 3200. Unchanged — was already int.

    focal_length: Optional[float] = Field(default=None)
    # ExifTool -n: float in mm. 26.0, 77.0, 4.2.
    # Without -n it would be "26.0 mm" (str requiring parsing).

    flash: Optional[int] = Field(default=None)
    # ExifTool -n: int bitmask per EXIF spec.
    # 0=no flash, 1=flash fired, 24=auto mode did not fire.
    # MetadataVault decodes this bitmask. Storing as int preserves that.

    white_balance: Optional[int] = Field(default=None)
    # ExifTool -n: int. 0=auto, 1=manual.
    # MetadataVault interprets this numerically.

    orientation: Optional[int] = Field(default=None)
    # ExifTool -n: int 1–8 per EXIF orientation spec.
    # 1=normal, 3=180°, 6=90°CW, 8=90°CCW.
    # MetadataVault converts this to a human-readable rotation label.

    # ── PLATFORM / SOFTWARE ───────────────────────────────────────
    processing_software: Optional[str] = Field(default=None)
    creator_tool: Optional[str] = Field(default=None)

    # ── COMPLETE RAW OUTPUT ───────────────────────────────────────
    all_fields: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Complete unfiltered ExifTool output for this image. "
            "Stored alongside named fields so future engines can access "
            "tags not yet in EXIFTOOL_FIELD_MAP without a second "
            "subprocess call. Memory cost is negligible for prototype scale."
        )
    )
    # default_factory=dict: creates a fresh empty dict per instance.
    # Never use default={} — Pydantic would share one dict across all instances.

    # ── EXTRACTION METADATA ───────────────────────────────────────
    extraction_success: bool = Field(
        default=False,
        description=(
            "True if ExifTool ran without process error, regardless of "
            "how many metadata fields were found. False only when ExifTool "
            "itself failed (not installed, timed out, parse error, etc.). "
            "An image with zero metadata fields is extraction_success=True "
            "with field_count=0 — that is a valid and common result."
        )
    )
    # FIX 3: Semantics corrected. extraction_success now means
    # 'did the process run cleanly' not 'did we find something'.
    # field_count=0 communicates 'nothing found'.
    # extraction_success=False communicates 'process failed'.

    extraction_error: Optional[str] = Field(default=None)
    field_count: int = Field(default=0)


# ─────────────────────────────────────────────────────────────────
# EXIFTOOL FIELD MAP
# Maps ExifTool PascalCase output keys to RawMetadata snake_case fields.
# ─────────────────────────────────────────────────────────────────

EXIFTOOL_FIELD_MAP: Dict[str, str] = {
    # GPS
    "GPSLatitude":     "gps_latitude",
    "GPSLongitude":    "gps_longitude",
    "GPSAltitude":     "gps_altitude",
    "GPSLatitudeRef":  "gps_latitude_ref",
    "GPSLongitudeRef": "gps_longitude_ref",
    "GPSDateStamp":    "gps_date_stamp",
    "GPSTimeStamp":    "gps_time_stamp",

    # Device
    "Make":            "device_make",
    "Model":           "device_model",
    "Software":        "device_software",
    "LensMake":        "lens_make",
    "LensModel":       "lens_model",

    # Timestamps
    "DateTimeOriginal":  "datetime_original",
    "DateTimeDigitized": "datetime_digitized",
    "CreateDate":        "create_date",
    "ModifyDate":        "modify_date",

    # Content
    "ImageDescription": "image_description",
    "UserComment":      "user_comment",
    "Artist":           "artist",
    "Copyright":        "copyright",
    "XPComment":        "xp_comment",
    "XPAuthor":         "xp_author",
    "XPSubject":        "xp_subject",
    "XPKeywords":       "xp_keywords",

    # File
    "FileName":         "file_name",
    "FileSize":         "file_size",
    "FileType":         "file_type",
    "MIMEType":         "mime_type",

    # Camera settings
    "ExposureTime":     "exposure_time",
    "FNumber":          "f_number",
    "ISO":              "iso",
    "FocalLength":      "focal_length",
    "Flash":            "flash",
    "WhiteBalance":     "white_balance",
    "Orientation":      "orientation",

    # Platform
    "ProcessingSoftware": "processing_software",
    "CreatorTool":        "creator_tool",
}


# ─────────────────────────────────────────────────────────────────
# CUSTOM EXCEPTIONS
# Three specific failure modes, each diagnosable independently.
# ─────────────────────────────────────────────────────────────────

class ExifToolNotFoundError(Exception):
    """
    Raised when the exiftool binary is not found on the system PATH.
    This is a configuration error — ExifTool must be installed.
    Verify installation: exiftool -ver
    Install on macOS:         brew install exiftool
    Install on Ubuntu/Debian: apt-get install libimage-exiftool-perl
    Install on Windows:       download from https://exiftool.org
    """
    pass


class ExifToolExecutionError(Exception):
    """
    Raised when ExifTool runs but returns a non-zero exit code,
    or when the subprocess times out.
    Could indicate: corrupted image file, unsupported format variant,
    permission error on the temp file, or ExifTool hanging.
    """
    pass


class ExifToolParseError(Exception):
    """
    Raised when ExifTool's stdout cannot be parsed or has an
    unexpected structure. Distinct from:
    - ExifToolExecutionError (process-level failure)
    - Zero-metadata images (which return empty dict, not an error)

    Cases that raise this:
    - ExifTool returned completely empty stdout (abnormal)
    - ExifTool returned invalid JSON (should not happen in practice)
    - ExifTool returned valid JSON but not a list (unexpected structure)
    - ExifTool returned an empty JSON array [] (abnormal)
    """
    # FIX 2: New exception class added to distinguish parse/structure
    # errors from genuine zero-metadata images.
    pass


# ─────────────────────────────────────────────────────────────────
# METADATA EXTRACTOR
# ─────────────────────────────────────────────────────────────────

class MetadataExtractor:
    """
    Extracts all metadata from an image using ExifTool.

    Writes PrivoFrame.content to a temporary file, runs ExifTool,
    parses the JSON output, maps fields to RawMetadata, and returns
    the structured result.

    ExifTool must be installed and available on the system PATH.
    Verify with: exiftool -ver

    USAGE IN analyze.py
    --------------------
    extractor = MetadataExtractor()
    raw_metadata = extractor.extract(session.privo_frame)
    # Then pass raw_metadata to MetadataVault for classification
    """

    def extract(self, frame: PrivoFrame) -> RawMetadata:
        """
        Runs ExifTool against the image bytes in PrivoFrame.

        PARAMETERS
        ----------
        frame : PrivoFrame
            The validated input from the Trigger Engine.
            We read frame.content (the raw image bytes).
            We read frame.filename (used in log messages only).

        RETURNS
        -------
        RawMetadata
            Always returns a RawMetadata object — never raises.

            extraction_success=True, field_count=0:
                ExifTool ran cleanly. Image has no metadata.
                Common for images processed by messaging apps.

            extraction_success=True, field_count>0:
                ExifTool ran cleanly. Metadata found and mapped.

            extraction_success=False, extraction_error set:
                ExifTool failed at some stage (not installed,
                timed out, output malformed). Pipeline continues
                but MetadataVault receives no findings.

            WHY NEVER RAISE FROM extract()?
            --------------------------------
            Metadata extraction failure must not kill the pipeline.
            A photo with no EXIF (stripped by a messaging app) is a
            valid image. Detection and risk scoring still run.
            The user sees a note that metadata could not be read.
            The pipeline continues — it does not abort.

        STEPS
        -----
        1. Write frame.content bytes to a NamedTemporaryFile
        2. Run ExifTool: exiftool -j -n <temp_path>
        3. Parse ExifTool stdout (distinguishing error cases from
           genuine zero-metadata images)
        4. Map ExifTool keys to RawMetadata fields via EXIFTOOL_FIELD_MAP
        5. Store complete unfiltered output in all_fields
        6. Delete the temp file (always, in finally block)
        7. Return RawMetadata
        """
        logger.info(
            f"Metadata Extractor: starting extraction | "
            f"file='{frame.filename}' | "
            f"size={frame.size_bytes} bytes"
        )

        temp_path: Optional[str] = None

        try:
            # ── STEP 1: Write bytes to temp file ──────────────────
            temp_path = self._write_temp_file(frame.content, frame.filename)

            # ── STEP 2: Run ExifTool ───────────────────────────────
            raw_json = self._run_exiftool(temp_path)

            # ── STEP 3: Parse JSON output ──────────────────────────
            # Raises ExifToolParseError for malformed/unexpected output.
            # Returns {} for genuinely empty metadata (valid case).
            exif_data = self._parse_exiftool_output(raw_json)

            # ── STEP 4 & 5: Map fields to RawMetadata ─────────────
            raw_metadata = self._map_to_raw_metadata(exif_data)

            logger.info(
                f"Metadata Extractor: extraction complete | "
                f"fields_found={raw_metadata.field_count} | "
                f"has_gps={raw_metadata.gps_latitude is not None} | "
                f"success={raw_metadata.extraction_success}"
            )

            return raw_metadata

        except ExifToolNotFoundError as exc:
            logger.error(f"Metadata Extractor: ExifTool not found — {exc}")
            return RawMetadata(
                extraction_success=False,
                extraction_error=str(exc)
            )

        except ExifToolExecutionError as exc:
            logger.error(f"Metadata Extractor: ExifTool execution failed — {exc}")
            return RawMetadata(
                extraction_success=False,
                extraction_error=str(exc)
            )

        except ExifToolParseError as exc:
            # FIX 2: ExifToolParseError now caught separately.
            # This is a process-level anomaly, not a "no metadata" result.
            logger.error(f"Metadata Extractor: output parse error — {exc}")
            return RawMetadata(
                extraction_success=False,
                extraction_error=str(exc)
            )

        except Exception as exc:
            logger.error(
                f"Metadata Extractor: unexpected error — {exc}",
                exc_info=True
            )
            return RawMetadata(
                extraction_success=False,
                extraction_error=f"Unexpected error: {str(exc)}"
            )

        finally:
            # ── STEP 6: Always clean up the temp file ─────────────
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                    logger.debug(
                        f"Metadata Extractor: temp file deleted — {temp_path}"
                    )
                except OSError as e:
                    logger.warning(
                        f"Metadata Extractor: could not delete temp file — {e}"
                    )

    # ── PRIVATE METHODS ───────────────────────────────────────────

    def _write_temp_file(self, content: bytes, filename: Optional[str]) -> str:
        """
        Writes image bytes to a named temporary file.

        WHY NamedTemporaryFile WITH delete=False?
        ------------------------------------------
        ExifTool needs to open the file by path after Python closes it.
        On Windows, a file held open by one process cannot be opened
        by another. delete=False lets Python close it cleanly, then
        ExifTool opens it, then we delete it in the finally block.
        This pattern works identically on all platforms.

        The suffix preserves the original extension so ExifTool can use
        it as a format hint alongside the magic bytes in the file.

        RETURNS
        -------
        str — absolute path to the temp file.
        """
        suffix = ""
        if filename:
            _, ext = os.path.splitext(filename)
            suffix = ext  # e.g. ".jpg", ".heic"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            temp_path = tmp.name
            # tmp.name: full absolute path, e.g. /tmp/tmpA3F8B21C.jpg
            # File is closed when the with block exits, making it
            # available for ExifTool to open by path.

        logger.debug(f"Metadata Extractor: temp file written — {temp_path}")
        return temp_path

    def _run_exiftool(self, file_path: str) -> str:
        """
        Runs ExifTool against the given file path.

        COMMAND: exiftool -j -n <file_path>
            -j  → JSON output. Returns a list: [{ field: value, ... }]
            -n  → Numeric values. GPS as float, flash as int bitmask,
                  exposure time as float seconds, orientation as int.

        RETURNS
        -------
        str — ExifTool's raw stdout (a JSON string).

        RAISES
        ------
        ExifToolNotFoundError  → binary not on PATH
        ExifToolExecutionError → non-zero exit code or timeout
        """
        try:
            result = subprocess.run(
                ["exiftool", "-j", "-n", file_path],
                # List form — never shell=True with user-derived paths.
                # Shell injection risk if file_path contains special chars.
                capture_output=True,
                # Captures stdout and stderr. Without this, ExifTool
                # output prints to the terminal instead of being readable.
                text=True,
                # Decodes stdout/stderr as UTF-8 strings.
                # Without this, result.stdout would be bytes.
                timeout=30,
                # If ExifTool takes more than 30 seconds, raise
                # TimeoutExpired. Prevents a hung process from blocking
                # the API indefinitely.
            )

        except FileNotFoundError:
            raise ExifToolNotFoundError(
                "ExifTool binary not found on PATH. "
                "Verify installation with: exiftool -ver"
            )

        except subprocess.TimeoutExpired:
            raise ExifToolExecutionError(
                f"ExifTool timed out after 30 seconds on: {file_path}"
            )

        if result.returncode != 0:
            raise ExifToolExecutionError(
                f"ExifTool exited with code {result.returncode}: "
                f"{result.stderr.strip()}"
            )

        return result.stdout

    def _parse_exiftool_output(self, raw_json: str) -> Dict[str, Any]:
        """
        Parses ExifTool's JSON stdout into a Python dict.

        FOUR DISTINCT CASES
        -------------------
        Case A — ExifTool ran, image has no metadata:
            ExifTool returns [{"SourceFile": "..."}] or similar.
            parsed[0] contains only internal ExifTool fields.
            Returns the dict (almost empty). Not an error.
            _map_to_raw_metadata produces extraction_success=True,
            field_count=0 (or a small count of SourceFile etc.).

        Case B — ExifTool returned empty stdout:
            Abnormal. ExifTool always writes something to stdout
            when it processes a file. Empty stdout suggests a
            silent process failure.
            Raises ExifToolParseError.

        Case C — ExifTool returned malformed/invalid JSON:
            Should not happen — ExifTool's -j output is well-tested.
            If it does, indicates corrupted ExifTool installation.
            Raises ExifToolParseError.

        Case D — ExifTool returned valid JSON but unexpected structure:
            ExifTool -j always returns a list. Non-list or empty list
            is anomalous.
            Raises ExifToolParseError.

        WHY RAISE FOR B/C/D INSTEAD OF RETURNING {}?
        ----------------------------------------------
        Returning {} for all cases merges process errors with genuine
        zero-metadata images, making them indistinguishable in logs
        and in extraction_success semantics. Raising specific exceptions
        lets the caller (extract()) label them correctly and produce a
        clear extraction_error message for debugging.
        """

        # Case B: completely empty stdout
        if not raw_json or not raw_json.strip():
            raise ExifToolParseError(
                "ExifTool returned empty stdout. "
                "Expected a JSON array — process may have failed silently."
            )

        # Case C: malformed JSON
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise ExifToolParseError(
                f"ExifTool returned invalid JSON: {exc}. "
                f"Raw output (first 200 chars): {raw_json[:200]}"
            )

        # Case D: unexpected structure
        if not isinstance(parsed, list):
            raise ExifToolParseError(
                f"ExifTool JSON was not a list. "
                f"Got: {type(parsed).__name__}"
            )

        if len(parsed) == 0:
            raise ExifToolParseError(
                "ExifTool returned an empty JSON array []. "
                "Expected at least one entry for the processed file."
            )

        # Case A: valid output — may have many fields or very few.
        # parsed[0] is the metadata dict for the one file we passed.
        return parsed[0]

    def _map_to_raw_metadata(self, exif_data: Dict[str, Any]) -> RawMetadata:
        """
        Maps ExifTool's PascalCase fields to RawMetadata snake_case fields.

        Uses EXIFTOOL_FIELD_MAP to translate key names.
        Stores the complete unfiltered output in all_fields.

        PARAMETERS
        ----------
        exif_data : Dict[str, Any]
            The raw dict from ExifTool for one file.
            May be empty (valid zero-metadata case) or full.

        RETURNS
        -------
        RawMetadata with:
            - Matched named fields populated from EXIFTOOL_FIELD_MAP
            - all_fields = complete unfiltered dict
            - extraction_success = True (ExifTool ran — this method
              is only called after successful parsing)
            - field_count = len(exif_data)
        """
        # FIX 3: Empty exif_data is now extraction_success=True.
        # ExifTool ran cleanly and found no metadata — valid outcome.
        # field_count=0 communicates "nothing found".
        # extraction_success=True communicates "process worked".
        if not exif_data:
            logger.info(
                "Metadata Extractor: image contains no metadata fields. "
                "This is normal for images processed by messaging apps."
            )
            return RawMetadata(
                extraction_success=True,
                extraction_error=None,
                field_count=0,
                all_fields={}
            )

        # Map ExifTool keys to RawMetadata fields
        field_assignments: Dict[str, Any] = {}

        for exif_key, raw_field_name in EXIFTOOL_FIELD_MAP.items():
            value = exif_data.get(exif_key)
            # dict.get returns None if key doesn't exist.
            # We only assign fields that ExifTool actually found.
            # Missing fields keep their RawMetadata defaults (None).
            if value is not None:
                field_assignments[raw_field_name] = value

        return RawMetadata(
            **field_assignments,
            # Unpacks only the fields ExifTool returned.
            # All other RawMetadata fields default to None.
            all_fields=exif_data,
            extraction_success=True,
            field_count=len(exif_data)
        )
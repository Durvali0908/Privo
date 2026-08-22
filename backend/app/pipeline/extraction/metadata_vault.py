"""
app/pipeline/extraction/metadata_vault.py

PURPOSE
-------
The Metadata Vault classifies raw metadata fields into structured
privacy findings — the first point in Privo's pipeline where raw
signals become actionable privacy intelligence.

The extractor asks: "What metadata is in this image?"
The vault asks:     "What does that metadata reveal?"

─────────────────────────────────────────────────────────────────────
WHAT IS A METADATA FINDING?
─────────────────────────────────────────────────────────────────────
A MetadataFinding is the atomic unit of privacy intelligence produced
by this stage. Each finding represents one specific piece of private
information that is embedded in the image's metadata.

Example:
    Field:       "GPSLatitude" + "GPSLongitude"
    Value:       "37.7749, -122.4194"
    Category:    LocationExposure
    Severity:    HIGH
    Explanation: "This image contains GPS coordinates that reveal
                  where it was captured."

This finding is then passed to:
    - Risk Scoring Engine → contributes to the overall risk score
    - Privacy Heatmap Engine → highlights affected regions
    - Interactive Protection UI → offers GPS removal as a protection

─────────────────────────────────────────────────────────────────────
WHICH EXPOSURE CATEGORIES METADATA CAN SERVE
─────────────────────────────────────────────────────────────────────
Metadata Vault only classifies against categories that metadata
can actually provide evidence for:

    LocationExposure  → GPS coordinates
    IdentityExposure  → device make/model, author annotations
    ActivityExposure  → timestamps, flash, software fingerprints
    ContactExposure   → artist, copyright, XP author/comment fields
    TravelExposure    → GPS + timestamp in combination

Categories requiring pixel-level analysis (ChildSafetyExposure,
EducationalExposure, WorkplaceExposure, FinancialExposure,
DocumentExposure) are NOT raised here. They belong to the
Detection Engine in pipeline/detection/.

─────────────────────────────────────────────────────────────────────
DESIGN PRINCIPLES
─────────────────────────────────────────────────────────────────────
1. Evidence-based only.
   A finding is raised only when a specific field is present
   with a non-null, non-empty value. No inference, no guessing.

2. Vault classifies only. It never modifies.
   Redaction, blurring, and removal belong to the Protection
   Modules (pipeline/protection/). The Vault is read-only.

3. Severity is field-type based, not value based.
   GPS coordinates are always HIGH — the Risk Scoring Engine
   contextualises severity against the broader session later.

4. Combination findings.
   Some findings are only meaningful in combination.
   GPS + timestamp together form a stronger TravelExposure finding
   than GPS alone. The Vault raises both individual findings AND
   the combination finding when applicable.

5. Human-readable explanations.
   Every finding includes an explanation written for a non-technical
   user. Explanations describe what the metadata field contains and
   why it is a privacy concern. They do not make claims about
   measurement accuracy or precision that cannot be verified from
   the metadata alone.

─────────────────────────────────────────────────────────────────────
NOTE ON field_count
─────────────────────────────────────────────────────────────────────
RawMetadata.field_count reflects the total number of fields ExifTool
returned, including ExifTool-internal fields such as SourceFile,
ExifToolVersion, and FilePermissions. It is a diagnostic measure of
how much raw data ExifTool found — not the number of fields the Vault
classifies. The Vault checks only the named fields defined in
RawMetadata (at most ~25 privacy-relevant fields regardless of how
many ExifTool fields were returned).

─────────────────────────────────────────────────────────────────────
HOW THIS FILE COMMUNICATES WITH OTHER MODULES
─────────────────────────────────────────────────────────────────────
Receives from:
    metadata_extractor.py → RawMetadata

Produces:
    List[MetadataFinding] → passed to SessionManager and analyze.py

Called by:
    app/api/v1/endpoints/analyze.py
        → after MetadataExtractor.extract()
        → results stored on session via SessionManager.update_metadata_findings()

FUTURE MODULES THAT WILL DEPEND ON THIS FILE
---------------------------------------------
- Risk Scoring Engine   → reads MetadataFinding.severity and .category
- Privacy Heatmap Engine→ metadata findings contribute to heatmap weight
- Interactive UI        → displays finding.explanation to the user
- Analytics Dashboard   → aggregates findings across sessions
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.pipeline.extraction.metadata_extractor import RawMetadata

logger = get_logger(__name__)
# __name__ = "app.pipeline.extraction.metadata_vault"
# Logger name = "privo.app.pipeline.extraction.metadata_vault"


# ─────────────────────────────────────────────────────────────────
# EXPOSURE CATEGORY ENUM
# ─────────────────────────────────────────────────────────────────

class ExposureCategory(str, Enum):
    """
    Privo's official exposure categories.

    WHY DEFINED HERE AND NOT IN A SHARED MODULE?
    ---------------------------------------------
    In Week 2, only the Metadata Vault uses these categories.
    When the Signal Classification Engine (pipeline/classification/)
    is built in a future week, this enum will be extracted to a
    shared location (e.g. app/core/categories.py) that all
    classification engines import from. It moves when a second
    module needs it — not before.

    WHY str, Enum?
    --------------
    str inheritance means each member serialises to a plain string
    in JSON: "location_exposure" not "ExposureCategory.LOCATION".
    """
    LOCATION    = "location_exposure"
    IDENTITY    = "identity_exposure"
    CHILD       = "child_safety_exposure"     # not raised by Vault
    EDUCATIONAL = "educational_exposure"      # not raised by Vault
    WORKPLACE   = "workplace_exposure"        # not raised by Vault
    FINANCIAL   = "financial_exposure"        # not raised by Vault
    ACTIVITY    = "activity_exposure"
    CONTACT     = "contact_exposure"
    DOCUMENT    = "document_exposure"         # not raised by Vault
    TRAVEL      = "travel_exposure"


class FindingSeverity(str, Enum):
    """
    Severity levels for privacy findings.

    LOW    → information is present but low risk in most contexts.
    MEDIUM → information that could contribute to identification or
             tracking in combination with other signals.
    HIGH   → information that directly exposes private details
             with minimal additional context required.
    """
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


# ─────────────────────────────────────────────────────────────────
# METADATA FINDING
# ─────────────────────────────────────────────────────────────────

class MetadataFinding(BaseModel):
    """
    One specific piece of private information found in image metadata.

    HOW THIS TRAVELS THROUGH THE PIPELINE
    ---------------------------------------
    MetadataVault.classify() → List[MetadataFinding]
        → serialised to List[dict] via .model_dump()
        → stored on SessionData.metadata_findings
        → deserialised in analyze.py when building the API response
        → sent to React as part of AnalysisResponse (Week 2 extension)

    FIELDS
    ------
    category : ExposureCategory
        Which of Privo's 10 exposure categories this finding serves.

    severity : FindingSeverity
        LOW / MEDIUM / HIGH based on field type, not field value.

    field_name : str
        The metadata field(s) that produced this finding.
        Used by the Protection Module to know which field to remove.

    value : str
        The actual value found, formatted as a human-readable string.
        Displayed in the Privo UI alongside the explanation.

    explanation : str
        A non-technical explanation of what this metadata reveals.
        Written for the end user. Displayed directly in React.
        Does not make claims about measurement accuracy or uniqueness
        that cannot be established from the metadata field alone.

    is_combination : bool
        True when this finding is raised by two or more fields together.
        Used by the Risk Scoring Engine to weight combination findings.
    """

    category: ExposureCategory
    severity: FindingSeverity
    field_name: str
    value: str
    explanation: str
    is_combination: bool = Field(default=False)


# ─────────────────────────────────────────────────────────────────
# METADATA VAULT
# ─────────────────────────────────────────────────────────────────

class MetadataVault:
    """
    Classifies RawMetadata fields into structured MetadataFindings.

    USAGE IN analyze.py
    --------------------
    vault = MetadataVault()
    findings = vault.classify(raw_metadata)
    session_manager.update_metadata_findings(
        session.session_id,
        [f.model_dump() for f in findings]
    )
    """

    def classify(self, raw: RawMetadata) -> List[MetadataFinding]:
        """
        Runs all classification checks against RawMetadata.

        Returns a flat list of all MetadataFindings raised.
        Returns an empty list if extraction_success is False,
        or if no privacy-relevant fields are present.

        PARAMETERS
        ----------
        raw : RawMetadata
            The structured output from MetadataExtractor.extract().
            raw.field_count is the total number of fields ExifTool
            returned (including internal ExifTool fields). The Vault
            checks only the named RawMetadata fields — a subset of
            what ExifTool extracted.

        RETURNS
        -------
        List[MetadataFinding]
            All privacy findings from metadata classification.
            May be empty — that itself is meaningful (clean metadata).
        """
        if not raw.extraction_success:
            logger.warning(
                "Metadata Vault: skipping classification — "
                "extraction was not successful. "
                f"Reason: {raw.extraction_error}"
            )
            return []

        # FIX 1: Log wording corrected.
        # raw.field_count is total ExifTool fields (including internal ones).
        # The Vault checks ~25 named privacy-relevant fields, not all of them.
        # The log now reflects what the Vault actually does.
        logger.info(
            f"Metadata Vault: classifying privacy-relevant fields | "
            f"exiftool_field_count={raw.field_count}"
        )

        findings: List[MetadataFinding] = []

        findings.extend(self._check_location(raw))
        findings.extend(self._check_identity(raw))
        findings.extend(self._check_activity(raw))
        findings.extend(self._check_contact(raw))
        findings.extend(self._check_travel(raw))

        logger.info(
            f"Metadata Vault: classification complete | "
            f"findings={len(findings)} | "
            f"categories={list({f.category.value for f in findings})}"
        )

        return findings

    # ── PRIVATE CLASSIFICATION CHECKS ────────────────────────────

    def _check_location(self, raw: RawMetadata) -> List[MetadataFinding]:
        """
        Checks for GPS-based location exposure.

        FINDINGS RAISED
        ---------------
        1. GPS coordinates (HIGH) — if lat + lon both present
        2. GPS altitude (LOW)     — additional positional data
        3. GPS timestamp (LOW)    — time the GPS fix was recorded
        """
        findings: List[MetadataFinding] = []

        if raw.gps_latitude is not None and raw.gps_longitude is not None:
            # Apply latitude/longitude reference sign correction.
            # ExifTool -n returns GPSLatitude and GPSLongitude as always
            # positive. The Ref fields carry the hemisphere sign.
            lat = raw.gps_latitude
            lon = raw.gps_longitude

            if raw.gps_latitude_ref and raw.gps_latitude_ref.upper() == "S":
                lat = -lat
            if raw.gps_longitude_ref and raw.gps_longitude_ref.upper() == "W":
                lon = -lon

            findings.append(MetadataFinding(
                category=ExposureCategory.LOCATION,
                severity=FindingSeverity.HIGH,
                field_name="GPSLatitude + GPSLongitude",
                value=f"{lat:.6f}, {lon:.6f}",
                # 6 decimal places used for display consistency.
                # This reflects the formatting resolution of the output,
                # not the measurement accuracy of the GPS hardware.
                # FIX 2A: Removed the erroneous "≈ 11cm precision" comment.
                explanation=(
                    "This image contains GPS coordinates that reveal where "
                    "it was captured. The actual location accuracy depends "
                    "on the device and conditions at the time of capture, "
                    "but GPS-tagged images can expose the capture location "
                    "with potentially high precision."
                )
                # FIX 2B: Removed "to within a few metres" accuracy claim.
                # The explanation now describes what the data field contains
                # and its potential risk without asserting a specific accuracy
                # figure that Privo cannot verify from the metadata alone.
            ))

            logger.debug(
                f"Metadata Vault: GPS found — "
                f"lat={lat:.4f}, lon={lon:.4f}"
            )

        if raw.gps_altitude is not None:
            findings.append(MetadataFinding(
                category=ExposureCategory.LOCATION,
                severity=FindingSeverity.LOW,
                field_name="GPSAltitude",
                value=f"{raw.gps_altitude:.1f} metres",
                explanation=(
                    "This image contains altitude data. Combined with GPS "
                    "coordinates, this provides additional positional context "
                    "about where the image was captured."
                )
            ))

        if raw.gps_date_stamp is not None or raw.gps_time_stamp is not None:
            gps_time_value = " ".join(filter(None, [
                raw.gps_date_stamp,
                raw.gps_time_stamp
            ]))
            findings.append(MetadataFinding(
                category=ExposureCategory.LOCATION,
                severity=FindingSeverity.LOW,
                field_name="GPSDateStamp + GPSTimeStamp",
                value=gps_time_value,
                explanation=(
                    "This image contains the time at which the GPS location "
                    "was recorded. This can be used to establish a "
                    "location-time record for this image."
                )
            ))

        return findings

    def _check_identity(self, raw: RawMetadata) -> List[MetadataFinding]:
        """
        Checks for identity-related exposure from device and annotation fields.

        FINDINGS RAISED
        ---------------
        1. Device make + model (MEDIUM)
        2. Device software     (LOW)
        3. Lens information    (LOW)
        4. Image description   (MEDIUM)
        5. User comment        (MEDIUM)
        """
        findings: List[MetadataFinding] = []

        if raw.device_make is not None or raw.device_model is not None:
            device_parts = filter(None, [raw.device_make, raw.device_model])
            device_value = " ".join(device_parts)

            findings.append(MetadataFinding(
                category=ExposureCategory.IDENTITY,
                severity=FindingSeverity.MEDIUM,
                field_name="Make + Model",
                value=device_value,
                explanation=(
                    "This image was taken with a device whose make and model "
                    "are recorded in the metadata. This information can be "
                    "used to correlate images taken by a device of the same "
                    "make and model across different platforms."
                )
                # FIX 3A: "same device" → "a device of the same make and model".
                # Make and model do not uniquely identify a physical unit.
                # A serial number would be required for unique identification.
                # The finding is still valid — make/model enables correlation —
                # but the wording no longer implies unique device fingerprinting.
            ))

        if raw.device_software is not None:
            findings.append(MetadataFinding(
                category=ExposureCategory.IDENTITY,
                severity=FindingSeverity.LOW,
                field_name="Software",
                value=raw.device_software,
                explanation=(
                    "This image contains the software version used to "
                    "capture or process it (e.g. iOS 17.2, Instagram 300.0). "
                    "This can identify the platform and app used."
                )
            ))

        if raw.lens_make is not None or raw.lens_model is not None:
            lens_parts = filter(None, [raw.lens_make, raw.lens_model])
            lens_value = " ".join(lens_parts)

            findings.append(MetadataFinding(
                category=ExposureCategory.IDENTITY,
                severity=FindingSeverity.LOW,
                field_name="LensMake + LensModel",
                value=lens_value,
                explanation=(
                    "This image contains lens information that reveals the "
                    "type of camera equipment used to capture it."
                )
                # FIX 3B: "specific camera equipment" → "type of camera equipment".
                # Make/model identifies the lens model, not a unique physical unit.
            ))

        if raw.image_description is not None and raw.image_description.strip():
            findings.append(MetadataFinding(
                category=ExposureCategory.IDENTITY,
                severity=FindingSeverity.MEDIUM,
                field_name="ImageDescription",
                value=raw.image_description.strip(),
                explanation=(
                    "This image contains an embedded description. "
                    "This may include personal information added by "
                    "the camera app or editing software."
                )
            ))

        if raw.user_comment is not None and raw.user_comment.strip():
            comment = raw.user_comment.strip()
            if comment and not all(c == '\x00' for c in comment):
                findings.append(MetadataFinding(
                    category=ExposureCategory.IDENTITY,
                    severity=FindingSeverity.MEDIUM,
                    field_name="UserComment",
                    value=comment,
                    explanation=(
                        "This image contains an embedded user comment. "
                        "This may include personal notes or identifiable text."
                    )
                ))

        return findings

    def _check_activity(self, raw: RawMetadata) -> List[MetadataFinding]:
        """
        Checks for activity-related exposure from timestamps and camera settings.

        FINDINGS RAISED
        ---------------
        1. Capture timestamp     (MEDIUM)
        2. Processing software   (LOW)
        3. Flash usage           (LOW)
        """
        findings: List[MetadataFinding] = []

        timestamp = raw.datetime_original or raw.create_date
        if timestamp is not None:
            findings.append(MetadataFinding(
                category=ExposureCategory.ACTIVITY,
                severity=FindingSeverity.MEDIUM,
                field_name="DateTimeOriginal",
                value=timestamp,
                explanation=(
                    "This image contains the exact date and time it was "
                    "captured. This reveals when the subject was at the "
                    "photographed location."
                )
            ))

        if raw.creator_tool is not None:
            findings.append(MetadataFinding(
                category=ExposureCategory.ACTIVITY,
                severity=FindingSeverity.LOW,
                field_name="CreatorTool",
                value=raw.creator_tool,
                explanation=(
                    "This image reveals the software used to edit or "
                    "process it. This can identify the apps or workflows "
                    "used by the photographer."
                )
            ))

        if raw.flash is not None:
            # Decode EXIF flash bitmask.
            # Bit 0: 1 = flash fired, 0 = flash did not fire.
            # Remaining bits encode return detection, mode, red-eye reduction.
            flash_fired = bool(raw.flash & 1)
            flash_description = "Flash fired" if flash_fired else "Flash did not fire"

            findings.append(MetadataFinding(
                category=ExposureCategory.ACTIVITY,
                severity=FindingSeverity.LOW,
                field_name="Flash",
                value=f"{flash_description} (raw value: {raw.flash})",
                explanation=(
                    "This image contains flash usage data. This can "
                    "indicate whether the photo was taken indoors or "
                    "in low-light conditions."
                )
            ))

        return findings

    def _check_contact(self, raw: RawMetadata) -> List[MetadataFinding]:
        """
        Checks for contact-related exposure from author and copyright fields.

        FINDINGS RAISED
        ---------------
        1. Artist    (HIGH)   — often contains photographer's real name
        2. Copyright (MEDIUM) — may contain name and year
        3. XPAuthor  (HIGH)   — Windows-specific author tag
        4. XPComment (MEDIUM) — may contain personal information
        """
        findings: List[MetadataFinding] = []

        if raw.artist is not None and raw.artist.strip():
            findings.append(MetadataFinding(
                category=ExposureCategory.CONTACT,
                severity=FindingSeverity.HIGH,
                field_name="Artist",
                value=raw.artist.strip(),
                explanation=(
                    "This image contains a name in the Artist field. "
                    "This field is commonly used to record the photographer's "
                    "name and can directly identify who took the photo."
                )
            ))

        if raw.copyright is not None and raw.copyright.strip():
            findings.append(MetadataFinding(
                category=ExposureCategory.CONTACT,
                severity=FindingSeverity.MEDIUM,
                field_name="Copyright",
                value=raw.copyright.strip(),
                explanation=(
                    "This image contains a copyright notice which may "
                    "include the photographer's name and year."
                )
            ))

        if raw.xp_author is not None and raw.xp_author.strip():
            findings.append(MetadataFinding(
                category=ExposureCategory.CONTACT,
                severity=FindingSeverity.HIGH,
                field_name="XPAuthor",
                value=raw.xp_author.strip(),
                explanation=(
                    "This image contains an author name embedded by "
                    "Windows or a Windows-based application."
                )
            ))

        if raw.xp_comment is not None and raw.xp_comment.strip():
            findings.append(MetadataFinding(
                category=ExposureCategory.CONTACT,
                severity=FindingSeverity.MEDIUM,
                field_name="XPComment",
                value=raw.xp_comment.strip(),
                explanation=(
                    "This image contains an embedded comment that may "
                    "include personal or identifying information."
                )
            ))

        return findings

    def _check_travel(self, raw: RawMetadata) -> List[MetadataFinding]:
        """
        Checks for travel exposure — a combination finding.

        Raised only when BOTH GPS coordinates and a capture timestamp
        are present. Either alone is classified under its own category.
        Together they form a location-time record.

        FINDINGS RAISED
        ---------------
        1. GPS + timestamp combination (HIGH)
        """
        findings: List[MetadataFinding] = []

        has_gps = (
            raw.gps_latitude is not None and
            raw.gps_longitude is not None
        )
        has_timestamp = (
            raw.datetime_original is not None or
            raw.create_date is not None
        )

        if has_gps and has_timestamp:
            timestamp = raw.datetime_original or raw.create_date

            lat = raw.gps_latitude
            lon = raw.gps_longitude
            if raw.gps_latitude_ref and raw.gps_latitude_ref.upper() == "S":
                lat = -lat
            if raw.gps_longitude_ref and raw.gps_longitude_ref.upper() == "W":
                lon = -lon

            findings.append(MetadataFinding(
                category=ExposureCategory.TRAVEL,
                severity=FindingSeverity.HIGH,
                field_name="GPSLatitude + GPSLongitude + DateTimeOriginal",
                value=f"{lat:.6f}, {lon:.6f} at {timestamp}",
                explanation=(
                    "This image contains both GPS coordinates and a capture "
                    "timestamp. Together they form a location-time record "
                    "that can reveal where you were and when — potentially "
                    "contributing to a movement or travel profile."
                ),
                is_combination=True
            ))

        return findings
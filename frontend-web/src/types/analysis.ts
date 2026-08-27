/**
 * frontend/src/types/analysis.ts
 *
 * PURPOSE
 * -------
 * TypeScript interfaces that mirror the backend's API response schemas.
 *
 * Every type defined here corresponds exactly to a Pydantic model in:
 *   backend/app/schemas/analysis.py
 *
 * This file is the frontend's half of the API contract.
 * The backend defines what JSON it sends.
 * This file defines what TypeScript expects to receive.
 *
 * ─────────────────────────────────────────────────────────────────
 * WEEK 2 CHANGES FROM WEEK 1
 * ─────────────────────────────────────────────────────────────────
 * Added:
 *   ExposureCategory  → union type mirroring ExposureCategory enum
 *   FindingSeverity   → union type mirroring FindingSeverity enum
 *   MetadataFinding   → mirrors MetadataFindingSchema (backend)
 *   MetadataSummary   → mirrors MetadataSummary (backend)
 *
 * Extended:
 *   AnalysisResponse  → gains metadata: MetadataSummary | null
 *
 * Mirror path references updated in comments:
 *   InputSource  now mirrors app/pipeline/intake/trigger.py
 *   SessionStatus now mirrors app/pipeline/intake/session.py
 *
 * Unchanged from Week 1:
 *   InputSource, SessionStatus, ErrorCode (values identical)
 *   SettingsSnapshot (fields identical)
 *   AnalysisResponse (all Week 1 fields identical)
 *   ErrorDetail, FastAPIError (identical)
 *
 * ─────────────────────────────────────────────────────────────────
 * IMPORTANT RULE
 * ─────────────────────────────────────────────────────────────────
 * Never add fields here that don't exist in the backend schema.
 * Never remove fields without updating the backend schema first.
 * Both sides of the contract must always agree.
 *
 * ─────────────────────────────────────────────────────────────────
 * HOW THIS FILE COMMUNICATES WITH OTHER MODULES
 * ─────────────────────────────────────────────────────────────────
 * Imported by:
 *   src/lib/api.ts
 *     → return type of analyzeImage() is Promise<AnalysisResponse>
 *     → error handling uses ErrorDetail and FastAPIError
 *
 *   src/features/upload/useUpload.ts
 *     → state type: result: AnalysisResponse | null
 *
 *   src/features/upload/UploadZone.tsx
 *     → renders result fields including result.metadata
 *
 * FUTURE TYPES TO ADD IN THIS FILE
 * ----------------------------------
 *   DetectionResponse  → Week 3: detected regions and signal types
 *   RiskResponse       → Week 4: risk scores per exposure category
 *   HeatmapResponse    → Week 5: heatmap coordinates and overlay data
 *   ProtectionResponse → Week 6: applied protections and export path
 */


// ─────────────────────────────────────────────────────────────────
// SHARED LITERAL TYPES
// Constrain string fields to their exact allowed values.
// Mirror the str Enum types in the backend.
// ─────────────────────────────────────────────────────────────────

/**
 * The input source type for an analysis session.
 *
 * MIRRORS
 * -------
 * backend/app/pipeline/intake/trigger.py → class InputSource(str, Enum)
 *   GALLERY = "gallery"
 *   CAMERA  = "camera"
 *   VIDEO   = "video"
 *
 * WHY A UNION TYPE AND NOT string?
 * ---------------------------------
 * A typo like "galery" is a compile-time error here.
 * With plain string it would be a silent runtime bug.
 */
export type InputSource = "gallery" | "camera" | "video";

/**
 * The lifecycle status of an analysis session.
 *
 * MIRRORS
 * -------
 * backend/app/pipeline/intake/session.py → class SessionStatus(str, Enum)
 *   PENDING    = "pending"
 *   PROCESSING = "processing"
 *   COMPLETE   = "complete"
 *   TERMINATED = "terminated"
 */
export type SessionStatus = "pending" | "processing" | "complete" | "terminated";

/**
 * Machine-readable error codes from the Trigger Engine and endpoint handlers.
 *
 * MIRRORS
 * -------
 * backend/app/pipeline/intake/trigger.py → ValidationResult.error_code values
 * backend/app/api/v1/endpoints/analyze.py → HTTPException error_code values
 *
 * WHY A UNION TYPE AND NOT string?
 * ---------------------------------
 * When the backend adds a new error code, TypeScript flags every
 * switch/if block that uses ErrorCode — reminding you to handle
 * the new case before it becomes a silent runtime gap in the UI.
 */
export type ErrorCode =
    | "MISSING_FILE"
    | "MISSING_CONTENT"
    | "MISSING_EXTENSION"
    | "UNSUPPORTED_EXTENSION"
    | "FILE_TOO_LARGE"
    | "VALIDATION_FAILED"
    | "TRIGGER_ENGINE_ERROR"
    | "SESSION_CREATION_ERROR";

/**
 * Privo's official exposure categories.
 *
 * MIRRORS
 * -------
 * backend/app/pipeline/extraction/metadata_vault.py
 *   → class ExposureCategory(str, Enum)
 *
 * All ten official categories are listed — including those not
 * currently raised by the Metadata Vault. This ensures the frontend
 * is ready to render findings from future engines (Detection Engine,
 * Signal Classification Engine) without a type change to this file.
 *
 * Categories the Metadata Vault raises in Week 2:
 *   "location_exposure", "identity_exposure", "activity_exposure",
 *   "contact_exposure", "travel_exposure"
 *
 * Categories not yet raised (require pixel-level detection):
 *   "child_safety_exposure", "educational_exposure",
 *   "workplace_exposure", "financial_exposure", "document_exposure"
 */
export type ExposureCategory =
    | "location_exposure"
    | "identity_exposure"
    | "child_safety_exposure"
    | "educational_exposure"
    | "workplace_exposure"
    | "financial_exposure"
    | "activity_exposure"
    | "contact_exposure"
    | "document_exposure"
    | "travel_exposure";

/**
 * Severity level of a privacy finding.
 *
 * MIRRORS
 * -------
 * backend/app/pipeline/extraction/metadata_vault.py
 *   → class FindingSeverity(str, Enum)
 *   LOW    = "low"
 *   MEDIUM = "medium"
 *   HIGH   = "high"
 *
 * Used by the UI to choose badge colour and sort order.
 * HIGH findings are shown first and highlighted more prominently.
 */
export type FindingSeverity = "low" | "medium" | "high";


// ─────────────────────────────────────────────────────────────────
// SETTINGS SNAPSHOT
// Unchanged from Week 1.
// ─────────────────────────────────────────────────────────────────

/**
 * A read-only snapshot of the session settings.
 *
 * MIRRORS
 * -------
 * backend/app/schemas/analysis.py → class SettingsSnapshot(BaseModel)
 */
export interface SettingsSnapshot {
    /** UI theme: "light" | "dark" | "system" */
    theme: string;

    /** Analysis intensity: "fast" | "balanced" | "thorough" */
    scanning_mode: string;

    /** Whether metadata is included in analysis results. */
    metadata_retention: boolean;

    /** Whether this session is stored in analysis history. */
    analysis_history: boolean;

    /** Whether cloud AI processing is enabled. false = local only. */
    cloud_processing: boolean;
}


// ─────────────────────────────────────────────────────────────────
// WEEK 2 ADDITIONS — METADATA TYPES
// ─────────────────────────────────────────────────────────────────

/**
 * One privacy finding from the Metadata Vault.
 *
 * MIRRORS
 * -------
 * backend/app/schemas/analysis.py → class MetadataFindingSchema(BaseModel)
 *
 * NOTE: The backend has a MetadataFinding model in metadata_vault.py
 * (internal pipeline model) and a MetadataFindingSchema in schemas/
 * (public API model). The frontend only ever sees MetadataFindingSchema
 * via the HTTP response — this interface mirrors that schema.
 *
 * HOW THE FRONTEND USES THIS
 * ---------------------------
 * UploadZone.tsx renders each finding as a row showing:
 *   - severity badge (coloured: red=high, amber=medium, slate=low)
 *   - category label (e.g. "Location Exposure")
 *   - field_name (which metadata field was responsible)
 *   - value (the actual data found in the image)
 *   - explanation (shown as plain text to the user)
 *
 * Future: the Protection UI uses field_name to identify which field
 * to remove when the user clicks "Remove this finding".
 *
 * WEEK 2 JSON EXAMPLE
 * --------------------
 * {
 *   "category": "location_exposure",
 *   "severity": "high",
 *   "field_name": "GPSLatitude + GPSLongitude",
 *   "value": "19.075984, 72.877656",
 *   "explanation": "This image contains GPS coordinates...",
 *   "is_combination": false
 * }
 */
export interface MetadataFinding {
    /**
     * Exposure category this finding belongs to.
     * Typed as ExposureCategory so the UI can switch on it exhaustively.
     * Example: "location_exposure"
     */
    category: ExposureCategory;

    /**
     * Severity of this finding.
     * Used by the UI to choose badge colour and sort order.
     * HIGH findings sort first and use a red badge.
     */
    severity: FindingSeverity;

    /**
     * The metadata field(s) responsible for this finding.
     * Examples: "GPSLatitude + GPSLongitude", "Make + Model", "Artist"
     * Future: passed to the Protection Module to identify what to remove.
     */
    field_name: string;

    /**
     * The actual metadata value, formatted for display.
     * Examples: "19.075984, 72.877656", "Apple iPhone 15 Pro", "John Smith"
     * Displayed alongside the explanation in the findings panel.
     */
    value: string;

    /**
     * Non-technical explanation of what this metadata reveals.
     * Written by the backend for the end user — plain English.
     * Displayed directly in the React UI without modification.
     */
    explanation: string;

    /**
     * True when this finding was produced by two or more fields together.
     * Example: GPS coordinates + capture timestamp → travel_exposure.
     * False when produced by a single field alone.
     *
     * Future: the Risk Scoring Engine weights combination findings
     * more heavily than isolated findings. The UI may add a visual
     * indicator for combination findings (e.g. a "combined signal" label).
     */
    is_combination: boolean;
}

/**
 * Envelope for metadata extraction and classification results.
 *
 * MIRRORS
 * -------
 * backend/app/schemas/analysis.py → class MetadataSummary(BaseModel)
 *
 * WHY AN ENVELOPE AND NOT JUST MetadataFinding[]?
 * ------------------------------------------------
 * The frontend needs extraction_success to distinguish two cases
 * that both produce an empty findings array:
 *
 *   extraction_success=true,  findings=[] → image has clean metadata
 *   extraction_success=false, findings=[] → extraction failed
 *
 * These require different UI messages. Without extraction_success,
 * the frontend cannot tell them apart.
 *
 * total_findings is a convenience field — findings.length is equivalent
 * but this avoids the frontend having to measure the array.
 *
 * HOW TO RENDER IN UploadZone.tsx
 * --------------------------------
 * if (!result.metadata) {
 *   // metadata not yet available — Week 2 analyze always has it
 * } else if (!result.metadata.extraction_success) {
 *   // show: "Metadata could not be read"
 * } else if (result.metadata.total_findings === 0) {
 *   // show: "No metadata concerns found"
 * } else {
 *   // render result.metadata.findings list
 * }
 */
export interface MetadataSummary {
    /**
     * True if ExifTool ran without error, regardless of finding count.
     * False if ExifTool was not installed, timed out, or output was invalid.
     *
     * When false, findings will always be empty — but empty findings
     * does NOT imply the image has clean metadata. Use this field
     * to distinguish extraction failure from genuinely clean metadata.
     */
    extraction_success: boolean;

    /**
     * Total number of findings. Equals findings.length.
     * Provided as a convenience field for badge counts and summary text:
     *   "3 privacy concerns found"
     */
    total_findings: number;

    /**
     * The complete list of privacy findings from metadata classification.
     * Empty when extraction failed or the image has genuinely clean metadata.
     * Always check extraction_success before interpreting an empty array.
     */
    findings: MetadataFinding[];
}


// ─────────────────────────────────────────────────────────────────
// ANALYSIS RESPONSE — EXTENDED WITH METADATA
// ─────────────────────────────────────────────────────────────────

/**
 * Successful response from POST /api/v1/analyze.
 *
 * MIRRORS
 * -------
 * backend/app/schemas/analysis.py → class AnalysisResponse(BaseModel)
 *
 * WEEK 2 CHANGE
 * -------------
 * One new field added: metadata: MetadataSummary | null
 * All Week 1 fields are unchanged in name, type, and semantics.
 *
 * HOW THE FRONTEND READS THIS
 * ----------------------------
 * api.ts:         return type of analyzeImage() → Promise<AnalysisResponse>
 * useUpload.ts:   state: result: AnalysisResponse | null
 * UploadZone.tsx: renders all fields including result.metadata
 */
export interface AnalysisResponse {
    /**
     * Always true for AnalysisResponse.
     * Typed as literal true — TypeScript discriminated union.
     * TypeScript already knows this is true inside an AnalysisResponse.
     */
    success: true;

    /** Unique session identifier. Format: "PRIVO-SESSION-XXXXXXXX" */
    session_id: string;

    /**
     * Original filename from the upload.
     * null for camera and video frames (they have no filename).
     */
    filename: string | null;

    /** Which input type produced this session. */
    source: InputSource;

    /**
     * Current pipeline status.
     * Week 2: always "pending" — processing is synchronous.
     * Future: frontend polls this to show a progress indicator.
     */
    status: SessionStatus;

    /**
     * File size in bytes. null if unavailable.
     * Frontend formats for display: 2457600 → "2.3 MB"
     */
    file_size_bytes: number | null;

    /** Confirms default settings were loaded for this session. */
    settings_loaded: boolean;

    /** Human-readable status message for display. */
    message: string;

    /** Settings applied to this analysis session. */
    settings: SettingsSnapshot;

    /**
     * Metadata extraction and classification results.
     *
     * null     → metadata has not yet run (future async/polling context).
     * non-null → extraction ran; check extraction_success for outcome.
     *
     * In Week 2, the analyze endpoint always returns non-null here.
     * null is reserved for future async pipeline or polling endpoints
     * that reuse AnalysisResponse before metadata is available.
     */
    metadata: MetadataSummary | null;
}


// ─────────────────────────────────────────────────────────────────
// ERROR SHAPES
// Unchanged from Week 1.
// FastAPI wraps HTTPException detail inside { "detail": ... }.
// ─────────────────────────────────────────────────────────────────

/**
 * The inner error body produced by the backend.
 *
 * MIRRORS
 * -------
 * backend/app/schemas/analysis.py → class ErrorResponse(BaseModel)
 *
 * FastAPI wraps HTTPException.detail in a "detail" key:
 *   { "detail": { "success": false, "error_code": "...", ... } }
 *
 * This interface represents the INNER object.
 * FastAPIError (below) represents the outer wrapper.
 *
 * api.ts reads:
 *   const body: FastAPIError = await response.json()
 *   body.detail.error_code
 *   body.detail.message
 */
export interface ErrorDetail {
    /**
     * Always false for error responses.
     * Literal type — TypeScript discriminated union.
     */
    success: false;

    /**
     * Machine-readable error code.
     * Switch on this to show specific UI guidance:
     *   "FILE_TOO_LARGE"        → "Try compressing your image."
     *   "UNSUPPORTED_EXTENSION" → "JPG, PNG, WebP and HEIC only."
     */
    error_code: ErrorCode;

    /** Human-readable explanation. Displayed directly to the user. */
    message: string;

    /**
     * Optional additional context.
     * Always null in Week 2 — internal exception details are logged
     * server-side only and never sent to API clients.
     */
    detail: string | null;
}

/**
 * The full HTTP error response shape from FastAPI.
 *
 * FastAPI's HTTPException always produces:
 *   { "detail": <your detail value> }
 *
 * api.ts unwraps this:
 *   const body: FastAPIError = await response.json()
 *   const error: ErrorDetail = body.detail
 *
 * FUTURE: If a custom exception handler is added to main.py that
 * returns a flat ErrorDetail (no wrapper), this interface and the
 * unwrapping in api.ts must both be updated together.
 */
export interface FastAPIError {
    detail: ErrorDetail;
}
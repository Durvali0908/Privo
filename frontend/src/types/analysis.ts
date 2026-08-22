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
 * WHY THIS FILE EXISTS
 * --------------------
 * Without these types, every variable holding API data would be
 * typed as `any`. TypeScript would not catch:
 *   - Typos:       response.sesion_id    (silent bug)
 *   - Wrong fields: response.risk_score  (doesn't exist in Week 1)
 *   - Wrong usage:  response.valid === true (valid is on ErrorResponse, not AnalysisResponse)
 *
 * With these interfaces, all three mistakes above are compile-time errors.
 * The bug is caught before the browser ever runs the code.
 *
 * HOW THIS FILE COMMUNICATES WITH OTHER MODULES
 * ----------------------------------------------
 * Imported by:
 *   src/lib/api.ts
 *     → return type of analyzeImage() is Promise<AnalysisResponse>
 *     → error handling uses ErrorDetail (the wrapped FastAPI error shape)
 *
 *   src/features/upload/useUpload.ts
 *     → state type: result: AnalysisResponse | null
 *
 *   src/features/upload/UploadZone.tsx
 *     → prop type: result: AnalysisResponse | null
 *
 * FUTURE TYPES TO ADD IN THIS FILE
 * ----------------------------------
 * As Privo's pipeline grows, new response interfaces are added here:
 *   DetectionResponse  → Week 3: detected regions and signal types
 *   RiskResponse       → Week 4: risk scores per exposure category
 *   HeatmapResponse    → Week 5: heatmap coordinates and overlay data
 *   ProtectionResponse → Week 6: applied protections and export path
 *
 * Each maps to a new Pydantic schema added in:
 *   backend/app/schemas/analysis.py
 *
 * IMPORTANT RULE
 * --------------
 * Never add fields here that don't exist in the backend schema.
 * Never remove fields without updating the backend schema first.
 * Both sides of the contract must always agree.
 */


// ─────────────────────────────────────────────────────────────────
// SHARED LITERAL TYPES
// These constrain string fields to their exact allowed values.
// Mirrors the str Enum types in the backend.
// ─────────────────────────────────────────────────────────────────

/**
 * The input source type for an analysis session.
 *
 * WHY A UNION TYPE AND NOT JUST string?
 * --------------------------------------
 * If source were typed as string, you could write:
 *   if (response.source === "galery") { ... }   // typo, always false
 * TypeScript would not catch it.
 *
 * With InputSource as a union type:
 *   if (response.source === "galery") { ... }
 * TypeScript flags immediately: "galery" is not assignable to InputSource.
 *
 * MIRRORS
 * -------
 * backend/app/engine/trigger.py → class InputSource(str, Enum)
 *   GALLERY = "gallery"
 *   CAMERA  = "camera"
 *   VIDEO   = "video"
 */
export type InputSource = "gallery" | "camera" | "video";

/**
 * The lifecycle status of an analysis session.
 *
 * MIRRORS
 * -------
 * backend/app/engine/session.py → class SessionStatus(str, Enum)
 *   PENDING    = "pending"
 *   PROCESSING = "processing"
 *   COMPLETE   = "complete"
 *   TERMINATED = "terminated"
 */
export type SessionStatus = "pending" | "processing" | "complete" | "terminated";

/**
 * Machine-readable error codes produced by the Trigger Engine.
 * Used to show source-specific error messages in the UI.
 *
 * MIRRORS
 * -------
 * backend/app/engine/trigger.py → ValidationResult.error_code values
 * backend/app/api/v1/endpoints/analyze.py → HTTPException error_code values
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
// Using a union type here instead of leaving it as string means
// that if the backend adds a new error code, the TypeScript compiler
// will remind you to handle it in the UI wherever ErrorCode is used.


// ─────────────────────────────────────────────────────────────────
// SETTINGS SNAPSHOT
// The session settings returned with every successful response.
// ─────────────────────────────────────────────────────────────────

/**
 * A read-only snapshot of the session settings.
 *
 * MIRRORS
 * -------
 * backend/app/schemas/analysis.py → class SettingsSnapshot(BaseModel)
 *
 * HOW THE FRONTEND USES THIS
 * ---------------------------
 * Week 1: displayed as a JSON block in the response panel
 *         to confirm the pipeline loaded settings correctly.
 * Future: drives the Settings UI toggles and mode selectors.
 *         When the user changes scanning_mode in the UI,
 *         the new value is sent in the next analysis request.
 */
export interface SettingsSnapshot {
    /**
     * UI theme preference.
     * "light" | "dark" | "system"
     * Backend sends this but the frontend also reads from
     * localStorage for persistence between sessions.
     */
    theme: string;

    /**
     * Analysis intensity level.
     * "fast" | "balanced" | "thorough"
     * Displayed in the UI and sent in future analysis requests.
     */
    scanning_mode: string;

    /**
     * Whether metadata is included in analysis results.
     * Future: the Metadata Extractor reads this from SessionData.
     */
    metadata_retention: boolean;

    /**
     * Whether this session is stored in analysis history.
     * Future: the Memory Engine reads this from SessionData.
     */
    analysis_history: boolean;

    /**
     * Whether cloud AI processing is enabled.
     * false = local processing only (default, privacy-preserving).
     * Future: the Detection Engine reads this to choose model location.
     */
    cloud_processing: boolean;
}


// ─────────────────────────────────────────────────────────────────
// ANALYSIS RESPONSE
// The shape of a successful POST /api/v1/analyze response.
// ─────────────────────────────────────────────────────────────────

/**
 * Successful response from POST /api/v1/analyze.
 *
 * MIRRORS
 * -------
 * backend/app/schemas/analysis.py → class AnalysisResponse(BaseModel)
 *
 * HOW THE FRONTEND READS THIS
 * ----------------------------
 * api.ts:         return type of analyzeImage()
 * useUpload.ts:   stored in result state after a successful call
 * UploadZone.tsx: passed as prop to the result display section
 *
 * EXAMPLE JSON
 * ------------
 * {
 *   "success": true,
 *   "session_id": "PRIVO-SESSION-A3F8B21C",
 *   "filename": "photo.jpg",
 *   "source": "gallery",
 *   "status": "pending",
 *   "file_size_bytes": 2457600,
 *   "settings_loaded": true,
 *   "message": "photo.jpg received. Analysis pipeline ready.",
 *   "settings": { ... }
 * }
 */
export interface AnalysisResponse {
    /**
     * Always true for this interface.
     * (false responses use ErrorDetail — see below.)
     * The UI checks this first before reading other fields.
     */
    success: true;
    // Note: typed as literal `true`, not boolean.
    // This is a TypeScript discriminated union technique.
    // It means: if you have AnalysisResponse, you know success is always true.
    // You never need to write `if (response.success === true)` —
    // TypeScript already knows it is.

    /**
     * Unique session identifier.
     * Format: "PRIVO-SESSION-XXXXXXXX"
     * Stored by the frontend and sent in future requests:
     *   GET /api/v1/session/{session_id}/status
     *   POST /api/v1/session/{session_id}/protect
     */
    session_id: string;

    /**
     * Original filename from the upload.
     * null for camera and video frames (they have no filename).
     * Displayed as: "Analysing: photo.jpg"
     */
    filename: string | null;

    /**
     * Which input type produced this session.
     * "gallery" | "camera" | "video"
     * Used to decide which UI elements to show.
     * Example: camera source → show "Retake" instead of "Upload another".
     */
    source: InputSource;

    /**
     * Current pipeline status.
     * Week 1: always "pending" (no processing happens yet).
     * Future: frontend polls this to show a progress indicator.
     */
    status: SessionStatus;

    /**
     * File size in bytes.
     * null if size could not be determined.
     * Displayed as a human-readable string using formatBytes() from utils.ts.
     * Example: 2457600 → "2.4 MB"
     */
    file_size_bytes: number | null;

    /**
     * Confirms that default settings were loaded for this session.
     * Week 1: displayed as a pipeline status check in the result panel.
     * Future: if false, the UI shows a settings warning banner.
     */
    settings_loaded: boolean;

    /**
     * Human-readable status message for the frontend to display.
     * Examples:
     *   "photo.jpg received. Analysis pipeline ready."
     *   "Camera frame received. Analysis pipeline ready."
     */
    message: string;

    /**
     * The settings applied to this analysis session.
     * Used by the future Settings UI to display current configuration.
     */
    settings: SettingsSnapshot;
}


// ─────────────────────────────────────────────────────────────────
// ERROR SHAPES
// FastAPI wraps HTTPException detail inside { "detail": ... }.
// These interfaces reflect that exact wrapping.
// ─────────────────────────────────────────────────────────────────

/**
 * The inner error body produced by the backend.
 *
 * MIRRORS
 * -------
 * backend/app/schemas/analysis.py → class ErrorResponse(BaseModel)
 *
 * NOTE ON NESTING
 * ---------------
 * FastAPI wraps HTTPException.detail inside a "detail" key:
 *   { "detail": { "success": false, "error_code": "...", ... } }
 *
 * This interface represents the INNER object (the value of "detail").
 * The OUTER wrapper is FastAPIError below.
 * api.ts reads: error.detail.error_code, error.detail.message
 */
export interface ErrorDetail {
    /** Always false for error responses. */
    success: false;
    // Typed as literal `false` for the same reason success is literal `true`
    // on AnalysisResponse — TypeScript discriminated union.

    /**
     * Machine-readable error code.
     * The UI switches on this to show specific help messages.
     * Example:
     *   case "FILE_TOO_LARGE": show "Try compressing your image."
     *   case "UNSUPPORTED_EXTENSION": show "JPG, PNG, WebP and HEIC only."
     */
    error_code: ErrorCode;

    /**
     * Human-readable explanation.
     * Displayed directly to the user in the error panel.
     * Written by the backend to be user-friendly, not technical.
     */
    message: string;

    /**
     * Optional additional diagnostic context.
     * null for validation errors (message is sufficient).
     * May contain a short error summary for unexpected server errors.
     * In production this field should be suppressed on the backend
     * to avoid leaking internal implementation details.
     */
    detail: string | null;
}

/**
 * The full HTTP error response shape from FastAPI.
 *
 * WHY THIS WRAPPER EXISTS
 * -----------------------
 * FastAPI's HTTPException always wraps the detail in a "detail" key:
 *   { "detail": <your detail value> }
 *
 * This is FastAPI's built-in behaviour. The frontend must unwrap it.
 * api.ts does this unwrapping:
 *   const body: FastAPIError = await response.json()
 *   const errorDetail: ErrorDetail = body.detail
 *
 * FUTURE
 * ------
 * If a custom exception handler is added to backend/app/main.py that
 * returns a flat ErrorDetail directly (without the "detail" wrapper),
 * this interface and the unwrapping in api.ts must both be updated.
 */
export interface FastAPIError {
    detail: ErrorDetail;
}
/**
 * src/types/analysis.ts
 *
 * PURPOSE
 * -------
 * TypeScript interfaces that mirror the backend's API response schemas.
 *
 * Every interface here corresponds exactly to a Pydantic model in:
 *   backend/app/schemas/analysis.py
 *
 * This file is platform-agnostic — identical to the web version.
 * React Native and web TypeScript share the same type system.
 * No React Native-specific changes are needed here.
 *
 * ─────────────────────────────────────────────────────────────────
 * ARCHITECTURE NOTE
 * ─────────────────────────────────────────────────────────────────
 * This file is intentionally designed to require zero changes when:
 *   - The backend moves from laptop to cloud (URL changes in api.ts)
 *   - On-device processing is added (new optional fields added here)
 *   - New pipeline stages produce new response fields (added below)
 *
 * The API contract between phone and backend is defined here.
 * Both sides must agree. Never add fields that don't exist
 * in backend/app/schemas/analysis.py.
 *
 * ─────────────────────────────────────────────────────────────────
 * CURRENT BACKEND WEEK
 * ─────────────────────────────────────────────────────────────────
 * Mirrors Week 2 backend schemas:
 *   SettingsSnapshot      ← Week 1
 *   AnalysisResponse      ← Week 1, extended Week 2
 *   ErrorDetail           ← Week 1
 *   FastAPIError          ← Week 1
 *   ExposureCategory      ← Week 2
 *   FindingSeverity       ← Week 2
 *   MetadataFinding       ← Week 2
 *   MetadataSummary       ← Week 2
 *
 * FUTURE TYPES TO ADD (do not add until backend week arrives)
 *   DetectionSummary      ← Week 3
 *   DetectedRegion        ← Week 3
 *   RiskSummary           ← Week 5
 *   HeatmapData           ← Week 6
 *   ProtectionSummary     ← Week 7
 *
 * ─────────────────────────────────────────────────────────────────
 * HOW THIS FILE IS USED
 * ─────────────────────────────────────────────────────────────────
 * src/lib/api.ts
 *   → analyzeImage() returns Promise<AnalysisResponse>
 *   → error handling uses ErrorDetail, FastAPIError
 *
 * src/features/upload/useUpload.ts
 *   → state: result: AnalysisResponse | null
 *
 * src/features/upload/UploadZone.tsx
 *   → renders result including result.metadata findings
 */


// ─────────────────────────────────────────────────────────────────
// INPUT / SESSION TYPES
// ─────────────────────────────────────────────────────────────────

/**
 * Input source type for an analysis session.
 *
 * MIRRORS
 * -------
 * backend/app/pipeline/intake/trigger.py → class InputSource(str, Enum)
 *
 * FUTURE EXTENSIBILITY
 * --------------------
 * When Phase 2 (on-device processing) is added, a new source type
 * may be needed (e.g. "live_camera" for continuous frame analysis).
 * Add it here as a new union member — no other type changes needed.
 */
export type InputSource = "gallery" | "camera" | "video";

/**
 * Lifecycle status of an analysis session.
 *
 * MIRRORS
 * -------
 * backend/app/pipeline/intake/session.py → class SessionStatus(str, Enum)
 */
export type SessionStatus =
    | "pending"
    | "processing"
    | "complete"
    | "terminated";

/**
 * Machine-readable error codes from the backend.
 *
 * MIRRORS
 * -------
 * backend/app/pipeline/intake/trigger.py → ValidationResult.error_code
 * backend/app/api/v1/endpoints/analyze.py → HTTPException error_code values
 *
 * WHY A UNION TYPE
 * ----------------
 * When the backend adds a new error code, TypeScript flags every
 * switch statement using ErrorCode — preventing unhandled cases
 * from silently showing the wrong UI message.
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


// ─────────────────────────────────────────────────────────────────
// EXPOSURE CATEGORY AND SEVERITY
// ─────────────────────────────────────────────────────────────────

/**
 * Privo's ten official exposure categories.
 *
 * MIRRORS
 * -------
 * backend/app/pipeline/extraction/metadata_vault.py
 *   → class ExposureCategory(str, Enum)
 *
 * All ten categories are listed including those not yet raised
 * by the Metadata Vault. This ensures the UI is ready to render
 * findings from future engines without changing this file.
 *
 * Week 2 — Metadata Vault raises:
 *   location, identity, activity, contact, travel
 *
 * Future — Detection Engine will raise:
 *   child_safety, educational, workplace, financial, document
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
 *
 * Used by the UI to:
 *   - Choose badge colour (red=high, amber=medium, slate=low)
 *   - Sort findings (high first)
 *   - Determine overall risk indicator colour
 */
export type FindingSeverity = "low" | "medium" | "high";


// ─────────────────────────────────────────────────────────────────
// SETTINGS
// ─────────────────────────────────────────────────────────────────

/**
 * Read-only snapshot of session settings returned by the backend.
 *
 * MIRRORS
 * -------
 * backend/app/schemas/analysis.py → class SettingsSnapshot(BaseModel)
 *
 * Future: when the Settings screen is built (Week 9), the user's
 * preferences are sent back to the backend in each request header
 * or request body. This snapshot confirms what the backend applied.
 */
export interface SettingsSnapshot {
    theme: string;             // "light" | "dark" | "system"
    scanning_mode: string;     // "fast" | "balanced" | "thorough"
    metadata_retention: boolean;
    analysis_history: boolean;
    cloud_processing: boolean;
}


// ─────────────────────────────────────────────────────────────────
// METADATA FINDINGS (Week 2)
// ─────────────────────────────────────────────────────────────────

/**
 * One privacy finding from the Metadata Vault.
 *
 * MIRRORS
 * -------
 * backend/app/schemas/analysis.py → class MetadataFindingSchema(BaseModel)
 *
 * HOW THE UI USES THIS
 * --------------------
 * Each finding is rendered as a row in the findings panel:
 *   - severity badge (colour-coded)
 *   - category label (human-readable)
 *   - field_name (which metadata field)
 *   - value (the actual data found)
 *   - explanation (plain English, shown to the user)
 *
 * Future: field_name is passed to the Protection Module so the
 * user can tap "Remove this" and strip the specific field.
 */
export interface MetadataFinding {
    category: ExposureCategory;
    severity: FindingSeverity;
    field_name: string;
    value: string;
    explanation: string;
    is_combination: boolean;
}

/**
 * Envelope for metadata extraction and classification results.
 *
 * MIRRORS
 * -------
 * backend/app/schemas/analysis.py → class MetadataSummary(BaseModel)
 *
 * WHY extraction_success IS SEPARATE FROM findings.length
 * -------------------------------------------------------
 * findings=[] can mean two different things:
 *   extraction_success=true  + findings=[] → clean metadata (good)
 *   extraction_success=false + findings=[] → extraction failed (warn)
 *
 * The UI must show different messages for these two cases.
 * A plain array cannot encode this distinction.
 */
export interface MetadataSummary {
    extraction_success: boolean;
    total_findings: number;
    findings: MetadataFinding[];
}


// ─────────────────────────────────────────────────────────────────
// MAIN API RESPONSE
// ─────────────────────────────────────────────────────────────────

/**
 * Successful response from POST /api/v1/analyze.
 *
 * MIRRORS
 * -------
 * backend/app/schemas/analysis.py → class AnalysisResponse(BaseModel)
 *
 * DISCRIMINATED UNION
 * -------------------
 * success: true (literal) means TypeScript narrows this type
 * automatically when you check `if (response.success)`.
 * You never need to write `response.success === true`.
 *
 * FUTURE FIELDS
 * -------------
 * As the pipeline grows, new optional fields are added here:
 *   detection?: DetectionSummary    ← Week 3
 *   risk?: RiskSummary              ← Week 5
 *   heatmap?: HeatmapData           ← Week 6
 *   protection?: ProtectionSummary  ← Week 7
 *
 * All future fields are Optional so Week 2 responses (which do not
 * include them) remain valid without any frontend changes.
 */

// ─────────────────────────────────────────────────────────────────
// DETECTION TYPES (Week 3)
// ─────────────────────────────────────────────────────────────────

/**
 * Type of signal detected in the image.
 * Mirrors RegionType enum from roi_manager.py.
 */
export type RegionType = "face" | "qr_code" | "text";

/**
 * One detected privacy-relevant region.
 * Mirrors DetectedRegionSchema from schemas/analysis.py.
 * Coordinates are in pixels, origin = top-left corner.
 */
export interface DetectedRegion {
    x: number;
    y: number;
    width: number;
    height: number;
    region_type: RegionType;
    confidence: number;        // 0.0 – 1.0
    content: string | null;    // decoded QR content or OCR text; null for faces
}

/**
 * Detection engine results envelope.
 * Mirrors DetectionSummary from schemas/analysis.py.
 *
 * success=false → engine could not run (not that nothing was found).
 * face_count=0 with success=true → no faces detected, valid result.
 */
export interface DetectionSummary {
    success: boolean;
    image_width: number;
    image_height: number;
    face_count: number;
    qr_count: number;
    text_count: number;
    total_regions: number;
    regions: DetectedRegion[];
    error: string | null;
}

export interface AnalysisResponse {
    success: true;
    session_id: string;
    filename: string | null;
    source: InputSource;
    status: SessionStatus;
    file_size_bytes: number | null;
    settings_loaded: boolean;
    message: string;
    settings: SettingsSnapshot;

    // Week 2 — metadata extraction results
    // null when metadata has not yet run (future async pipeline)
    // In Week 2 the analyze endpoint always returns non-null here
    metadata: MetadataSummary | null;

    // Week 3 — detection engine results
    detection: DetectionSummary | null;

    // Week 5+ — risk scoring results
    // risk?: RiskSummary

    // Week 6+ — heatmap data
    // heatmap?: HeatmapData

    // Week 7+ — protection results
    // protection?: ProtectionSummary
}


// ─────────────────────────────────────────────────────────────────
// ERROR SHAPES
// ─────────────────────────────────────────────────────────────────

/**
 * Inner error body from the backend.
 *
 * MIRRORS
 * -------
 * backend/app/schemas/analysis.py → class ErrorResponse(BaseModel)
 *
 * FastAPI wraps HTTPException.detail in { "detail": <ErrorDetail> }.
 * api.ts reads: response.detail.error_code, response.detail.message
 *
 * detail field is always null in the current backend —
 * internal exception details are logged server-side only.
 */
export interface ErrorDetail {
    success: false;
    error_code: ErrorCode;
    message: string;
    detail: string | null;
}

/**
 * Full HTTP error response shape from FastAPI.
 *
 * FastAPI's HTTPException always produces:
 *   { "detail": <ErrorDetail> }
 *
 * api.ts unwraps this:
 *   const body: FastAPIError = await response.json()
 *   body.detail.error_code  → switch for UI guidance
 *   body.detail.message     → show to user
 */
export interface FastAPIError {
    detail: ErrorDetail;
}
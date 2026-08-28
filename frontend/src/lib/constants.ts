/**
 * src/lib/constants.ts
 *
 * PURPOSE
 * -------
 * Single source of truth for every hardcoded value in the Privo app.
 *
 * No component or hook should ever contain:
 *   - Raw URL strings
 *   - Magic numbers (file size limits, timeouts, etc.)
 *   - Repeated string literals (endpoint paths, error messages)
 *
 * Change a value here → every file that uses it updates automatically.
 *
 * ─────────────────────────────────────────────────────────────────
 * BACKEND URL — HOW IT WORKS
 * ─────────────────────────────────────────────────────────────────
 * During development (USB + adb reverse):
 *   Phone → USB → adb reverse → laptop:8000 → FastAPI
 *   URL = "http://localhost:8000"
 *   adb reverse tcp:8000 tcp:8000 must be running
 *
 * During WiFi testing (same network):
 *   URL = "http://192.168.x.x:8000"  ← your laptop's local IP
 *   Run: ipconfig on Windows, find IPv4 address under your WiFi adapter
 *
 * Future — cloud backend (Phase 2):
 *   URL = "https://api.privo.app"
 *   Change this one line. Nothing else in the app changes.
 *
 * ─────────────────────────────────────────────────────────────────
 * ARCHITECTURE NOTE
 * ─────────────────────────────────────────────────────────────────
 * This file has no imports and no React Native dependencies.
 * It is plain TypeScript — usable in any future migration
 * (on-device processing, cloud API, different framework).
 */


// ─────────────────────────────────────────────────────────────────
// BACKEND CONNECTION
// ─────────────────────────────────────────────────────────────────

/**
 * Base URL for all FastAPI requests.
 *
 * USB development (default):
 *   "http://localhost:8000"
 *   Requires: adb reverse tcp:8000 tcp:8000
 *
 * WiFi development (change when needed):
 *   "http://192.168.x.x:8000"
 *   Find your laptop IP: ipconfig → IPv4 Address under Wi-Fi adapter
 *
 * To switch between USB and WiFi:
 *   Change this one constant. No other file needs to change.
 */
export const API_BASE_URL = "http://localhost:8000";

/**
 * API version prefix. Matches backend router.py prefix="/api/v1".
 * If the backend ever adds /api/v2, create API_V2_PREFIX here.
 * Existing calls continue working on v1 without changes.
 */
export const API_V1_PREFIX = "/api/v1";

/**
 * Full constructed endpoint URLs.
 * Built from API_BASE_URL + API_V1_PREFIX so they stay in sync.
 *
 * Usage in api.ts:
 *   await axios.post(ENDPOINTS.ANALYZE, formData)
 */
export const ENDPOINTS = {
    ANALYZE: `${API_BASE_URL}${API_V1_PREFIX}/analyze`,
    // Future endpoints added here as backend weeks complete:
    // SESSION_STATUS: (id: string) => `${API_BASE_URL}${API_V1_PREFIX}/session/${id}/status`,
    // PROTECT:        (id: string) => `${API_BASE_URL}${API_V1_PREFIX}/session/${id}/protect`,
    // GALLERY:        `${API_BASE_URL}${API_V1_PREFIX}/gallery`,
} as const;
// `as const`: makes every value a readonly literal type.
// TypeScript infers ENDPOINTS.ANALYZE as the exact string,
// not just string. Prevents accidental mutation.


// ─────────────────────────────────────────────────────────────────
// FILE VALIDATION
// Must match backend/app/core/config.py values exactly.
// If the backend changes these limits, update here too.
// ─────────────────────────────────────────────────────────────────

/**
 * Maximum allowed upload size in bytes.
 * Matches: backend/app/core/config.py → max_file_size_mb = 20
 * 20 MB = 20 * 1024 * 1024 bytes
 *
 * Used by useUpload.ts to validate before sending to backend,
 * giving the user an immediate error without a network round-trip.
 */
export const MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024; // 20 MB

/**
 * Human-readable file size limit for error messages.
 * Keep in sync with MAX_FILE_SIZE_BYTES.
 */
export const MAX_FILE_SIZE_LABEL = "20 MB";

/**
 * Allowed image MIME types for expo-image-picker.
 * The picker uses these to filter the gallery.
 * Matches: backend/app/core/config.py → allowed_extensions
 */
export const ALLOWED_MIME_TYPES = [
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
] as const;

/**
 * Human-readable format list for UI display.
 * Used in error messages and the upload prompt.
 */
export const ALLOWED_FORMATS_LABEL = "JPG, PNG, WebP, HEIC";


// ─────────────────────────────────────────────────────────────────
// NETWORK
// ─────────────────────────────────────────────────────────────────

/**
 * Request timeout in milliseconds.
 *
 * Why 30 seconds?
 * The analysis pipeline on a laptop i3 with 8GB RAM can take
 * 6–15 seconds for heavy images (metadata + detection combined).
 * 30 seconds gives comfortable headroom without hanging indefinitely.
 *
 * This is passed to axios as the timeout option in api.ts.
 * If the request takes longer, axios throws a timeout error
 * which useUpload.ts catches and shows as a user-friendly message.
 */
export const REQUEST_TIMEOUT_MS = 30_000; // 30 seconds


// ─────────────────────────────────────────────────────────────────
// UI — SEVERITY COLOURS
// Used by StatusBadge and findings list to colour-code severity.
// Defined here so the colour system is consistent across all
// components without prop drilling or a theme provider.
// ─────────────────────────────────────────────────────────────────

/**
 * Background and text colours for each severity level.
 * Used in React Native StyleSheet — not Tailwind.
 *
 * These are intentionally defined as plain objects, not a theme.
 * When a design system is added later, these move there.
 * For now, one place for severity colours is sufficient.
 */
export const SEVERITY_COLOURS = {
    high: {
        background: "#3B0000",   // deep red background
        text: "#FF6B6B",   // bright red text
        border: "#7F0000",   // dark red border
    },
    medium: {
        background: "#2D1B00",   // deep amber background
        text: "#FFB347",   // amber text
        border: "#7A4500",   // dark amber border
    },
    low: {
        background: "#0F172A",   // dark slate background
        text: "#94A3B8",   // slate text
        border: "#1E293B",   // dark slate border
    },
} as const;

/**
 * Category display labels for the findings UI.
 * Maps ExposureCategory string values to human-readable labels.
 *
 * Used by the findings list to show "Location Exposure"
 * instead of "location_exposure" to the user.
 */
export const CATEGORY_LABELS: Record<string, string> = {
    location_exposure: "Location Exposure",
    identity_exposure: "Identity Exposure",
    child_safety_exposure: "Child Safety",
    educational_exposure: "Educational Content",
    workplace_exposure: "Workplace Information",
    financial_exposure: "Financial Information",
    activity_exposure: "Activity Exposure",
    contact_exposure: "Contact Information",
    document_exposure: "Document Exposure",
    travel_exposure: "Travel Pattern",
};


// ─────────────────────────────────────────────────────────────────
// APP IDENTITY
// ─────────────────────────────────────────────────────────────────

export const APP_NAME = "Privo";
export const APP_TAGLINE = "Think Before You Share";

/**
 * App version. Keep in sync with app.json → version.
 * Displayed in the Settings screen (Week 9).
 */
export const APP_VERSION = "0.1.0";
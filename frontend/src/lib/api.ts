/**
 * frontend/src/lib/api.ts
 *
 * PURPOSE
 * -------
 * The centralised HTTP client for all communication between
 * the React frontend and the FastAPI backend.
 *
 * Every network call the frontend makes goes through this file.
 * No component or hook ever calls fetch() directly.
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * Without a central API layer, fetch() calls would be scattered
 * across components and hooks. That creates several problems:
 *
 * - The base URL is repeated everywhere.
 *   Change it once here → all callers update automatically.
 *
 * - Error handling logic is duplicated.
 *   FastAPI's { "detail": ... } unwrapping happens once here,
 *   not in every component that calls the API.
 *
 * - Future auth headers (tokens, API keys) are added in one place.
 *   Without this layer, adding auth would require touching every file.
 *
 * - Mocking in tests is simple.
 *   Tests replace this module with a mock → all hooks get mock data.
 *   Without this layer, tests would need to intercept fetch() globally.
 *
 * HOW THIS FILE COMMUNICATES WITH OTHER MODULES
 * ----------------------------------------------
 * Imports from:
 *   src/types/analysis.ts
 *     → AnalysisResponse, FastAPIError, ErrorCode, ErrorDetail
 *       (used as return types and error payload types)
 *
 * Imported by:
 *   src/features/upload/useUpload.ts
 *     → calls analyzeImage(file) and handles PrivoApiError
 *
 * Future callers:
 *   src/features/session/useSession.ts
 *     → will call getSessionStatus(sessionId)
 *   src/features/protection/useProtection.ts
 *     → will call applyProtection(sessionId, regions)
 *   src/features/gallery/useGallery.ts
 *     → will call getGallery()
 *
 * FUTURE ADDITIONS TO THIS FILE
 * ------------------------------
 * Week 2+: getSessionStatus(sessionId: string): Promise<SessionStatusResponse>
 * Week 3+: pollAnalysisResult(sessionId: string): Promise<DetectionResponse>
 * Week 6+: applyProtection(sessionId: string, ...): Promise<ProtectionResponse>
 * Auth:    add Authorization header to all requests when auth is added
 */

import type {
    AnalysisResponse,
    FastAPIError,
    ErrorCode,
} from "../types/analysis";
// import type: TypeScript-only import — erased at compile time.
// These types are used only for type annotations, not at runtime.
// Using `import type` makes this explicit and allows bundlers to
// optimise the output by removing type-only imports entirely.
//
// AnalysisResponse → return type of analyzeImage()
// FastAPIError     → shape of error responses from FastAPI
// ErrorCode        → type of error.code on PrivoApiError


// ─────────────────────────────────────────────────────────────────
// CONFIGURATION
// ─────────────────────────────────────────────────────────────────

/**
 * Base URL for all FastAPI requests.
 *
 * HOW THIS VALUE IS SET
 * ----------------------
 * Vite exposes environment variables that start with VITE_ to the
 * frontend at build time via import.meta.env.
 *
 * In development: create frontend/.env.local and add:
 *   VITE_API_BASE_URL=http://localhost:8000
 *
 * If the variable is not set, falls back to http://localhost:8000
 * so the app works out of the box without any .env setup.
 *
 * WHY NOT HARDCODE http://localhost:8000 DIRECTLY?
 * -------------------------------------------------
 * In production or on a phone testing over WiFi, the backend is
 * not at localhost — it's at your machine's local IP address like
 * http://192.168.1.5:8000.
 *
 * Setting VITE_API_BASE_URL=http://192.168.1.5:8000 in .env.local
 * makes the entire app point to the right server without changing
 * any source code.
 *
 * Future: In production this becomes your deployed API domain.
 */
const API_BASE_URL: string =
    (import.meta.env.VITE_API_BASE_URL as string) ?? "http://localhost:8000";
// import.meta.env: Vite's way of accessing environment variables.
// The `as string` cast is needed because Vite types all env values
// as string | undefined. We know it's a string if it exists.
// The ?? operator returns the right side if the left is null or undefined.


// ─────────────────────────────────────────────────────────────────
// CUSTOM ERROR CLASS
// A typed error that carries structured information from the backend.
// ─────────────────────────────────────────────────────────────────

/**
 * A typed error thrown by all api.ts functions on failure.
 *
 * WHY A CUSTOM ERROR CLASS?
 * --------------------------
 * JavaScript's built-in Error only has a message string.
 * When the backend returns { "detail": { "error_code": "FILE_TOO_LARGE" } },
 * that information would be lost inside a generic Error message string.
 *
 * PrivoApiError carries the full structured error information:
 *   error.code     → "FILE_TOO_LARGE" (for UI logic)
 *   error.message  → "File is 45.2 MB. Maximum allowed size is 20 MB."
 *   error.detail   → optional extra context
 *   error.status   → HTTP status code (400, 500)
 *
 * HOW useUpload.ts CATCHES THIS
 * ------------------------------
 * try {
 *   const result = await analyzeImage(file)
 * } catch (err) {
 *   if (err instanceof PrivoApiError) {
 *     // err.code and err.message are available with full TypeScript types
 *     setErrorMessage(err.message)
 *   }
 * }
 *
 * The `instanceof PrivoApiError` check lets the hook distinguish
 * between a Privo API error (expected, handle gracefully) and an
 * unexpected JavaScript error (unexpected, handle differently).
 */
export class PrivoApiError extends Error {
    // WHY EXTEND Error?
    // Extending Error means PrivoApiError IS an Error.
    // catch (err) { } catches all errors.
    // instanceof PrivoApiError narrows it to our specific type.
    // This is standard JavaScript error hierarchy practice.

    /** HTTP status code: 400 for client errors, 500 for server errors. */
    public readonly status: number;

    /**
     * Machine-readable error code from the backend.
     * Matches ErrorCode union type from analysis.ts.
     * The UI switches on this to show specific guidance:
     *   "FILE_TOO_LARGE"        → "Try compressing your image."
     *   "UNSUPPORTED_EXTENSION" → "JPG, PNG, WebP and HEIC only."
     */
    public readonly code: ErrorCode;

    /**
     * Optional extra diagnostic context from the backend.
     * null for validation errors. May be present for server errors.
     */
    public readonly detail: string | null;

    constructor(
        status: number,
        code: ErrorCode,
        message: string,
        detail: string | null = null
    ) {
        super(message);
        // super(message): Calls Error's constructor with the message.
        // This sets this.message (inherited from Error) to our message.
        // Without this call, this.message would be undefined.

        this.name = "PrivoApiError";
        // Sets the error name shown in console and stack traces.
        // Without this, it would show as "Error" instead of "PrivoApiError".

        this.status = status;
        this.code = code;
        this.detail = detail;

        // Fix prototype chain for instanceof checks in TypeScript.
        // This is a known TypeScript quirk when extending built-in classes.
        // Without this line, `err instanceof PrivoApiError` can return false
        // in some environments even when err is a PrivoApiError.
        Object.setPrototypeOf(this, PrivoApiError.prototype);
    }
}


// ─────────────────────────────────────────────────────────────────
// INTERNAL HELPERS
// Private utilities used only within this file.
// ─────────────────────────────────────────────────────────────────

/**
 * Parses a failed HTTP response and throws a PrivoApiError.
 *
 * WHY A SEPARATE HELPER?
 * ----------------------
 * Every API function needs to handle HTTP errors the same way.
 * Extracting this logic into one helper means:
 * - The error handling is identical across all endpoints.
 * - When a new endpoint is added, it calls this helper — done.
 * - The FastAPI { "detail": ... } unwrapping happens in one place.
 *
 * WHAT IT DOES
 * ------------
 * 1. Tries to parse the response body as JSON.
 * 2. If it's a FastAPIError shape, extracts the structured error.
 * 3. If parsing fails (unexpected server error format), builds a
 *    generic PrivoApiError with the HTTP status and a safe message.
 *
 * HOW FastAPI ERROR UNWRAPPING WORKS
 * -----------------------------------
 * FastAPI wraps HTTPException detail in a "detail" key:
 *   { "detail": { "success": false, "error_code": "...", "message": "..." } }
 *
 * This function reads body.detail to get the inner ErrorDetail object.
 * Then it reads body.detail.error_code and body.detail.message.
 *
 * This matches what was documented in:
 *   backend/app/api/v1/endpoints/analyze.py (HTTP CONTRACT section)
 *   frontend/src/types/analysis.ts (FastAPIError interface)
 */
async function handleErrorResponse(response: Response): Promise<never> {
    // Promise<never>: This function ALWAYS throws — it never returns normally.
    // TypeScript's `never` type represents a value that never occurs.
    // Declaring Promise<never> communicates: "calling this always throws."
    // This helps TypeScript narrow control flow after the call site:
    // it knows execution never continues past this function.

    let errorCode: ErrorCode = "VALIDATION_FAILED";
    let errorMessage = "An unexpected error occurred. Please try again.";
    let errorDetail: string | null = null;

    try {
        const body = await response.json() as FastAPIError;
        // Cast to FastAPIError — our typed shape for FastAPI error responses.
        // FastAPIError has: { detail: { success, error_code, message, detail } }

        // Unwrap the "detail" wrapper FastAPI adds around HTTPException content.
        if (body.detail && typeof body.detail === "object") {
            errorCode = body.detail.error_code ?? "VALIDATION_FAILED";
            errorMessage = body.detail.message ?? errorMessage;
            errorDetail = body.detail.detail ?? null;
        }
    } catch {
        // JSON parsing failed — the response was not valid JSON.
        // This can happen if the server crashes before sending a response,
        // or if a proxy/firewall intercepts the request.
        // We fall through with the generic defaults set above.
        errorMessage = `Server returned an unreadable error (HTTP ${response.status}).`;
    }

    throw new PrivoApiError(response.status, errorCode, errorMessage, errorDetail);
}


// ─────────────────────────────────────────────────────────────────
// API FUNCTIONS
// One function per backend endpoint.
// Each function handles its own request construction and response
// parsing, and throws PrivoApiError on any failure.
// ─────────────────────────────────────────────────────────────────

/**
 * Uploads an image to the Privo analysis pipeline.
 *
 * ENDPOINT
 * --------
 * POST /api/v1/analyze
 * Content-Type: multipart/form-data
 * Body field name: "file"
 *
 * PARAMETERS
 * ----------
 * file : File
 *   The image file selected by the user.
 *   The File interface is built into browsers — it extends Blob
 *   and adds filename and lastModified. It comes from:
 *     - <input type="file"> → event.target.files[0]
 *     - drag-and-drop       → event.dataTransfer.files[0]
 *     - expo-image-picker   → converted to File for web, or sent
 *                             as FormData directly in React Native
 *
 * RETURNS
 * -------
 * Promise<AnalysisResponse>
 *   Resolves with the full typed response on success.
 *
 * THROWS
 * ------
 * PrivoApiError
 *   On any failure: validation error (400), server error (500),
 *   or network failure (no status code, message is generic).
 *
 * HOW TO CALL THIS
 * ----------------
 * In useUpload.ts:
 *   try {
 *     const result = await analyzeImage(file)
 *     setResult(result)          // result is AnalysisResponse
 *   } catch (err) {
 *     if (err instanceof PrivoApiError) {
 *       setError(err.message)    // show to user
 *     }
 *   }
 *
 * WHY NOT SET Content-Type MANUALLY?
 * ------------------------------------
 * When you pass a FormData object to fetch(), the browser sets
 * Content-Type: multipart/form-data; boundary=----WebKitFormBoundary...
 * automatically — including the boundary string that separates fields.
 *
 * If you set Content-Type: multipart/form-data manually (without the
 * boundary), FastAPI cannot parse the request body and returns 422.
 * Always let the browser set this header when using FormData.
 */
export async function analyzeImage(file: File): Promise<AnalysisResponse> {
    // Build the multipart/form-data request body.
    const formData = new FormData();
    // FormData: A browser built-in that builds multipart request bodies.
    // No import needed — it's part of the Web API.

    formData.append("file", file);
    // "file": must match the parameter name declared in the FastAPI endpoint:
    //   file: UploadFile = File(..., description="Image file to analyse")
    // If the names don't match, FastAPI returns 422 Unprocessable Entity.
    // The field name in FormData and the parameter name in FastAPI
    // must be identical strings.

    let response: Response;

    try {
        response = await fetch(`${API_BASE_URL}/api/v1/analyze`, {
            method: "POST",
            body: formData,
            // No Content-Type header — browser sets it automatically with boundary.
        });
    } catch (networkError) {
        // fetch() itself threw — this means a network failure:
        // - Backend server is not running
        // - No internet connection
        // - CORS preflight failed (browser blocked the request entirely)
        // - DNS resolution failed
        //
        // In all these cases, response never exists.
        // We throw a PrivoApiError with status 0 (no HTTP status available).
        throw new PrivoApiError(
            0,
            "VALIDATION_FAILED",
            "Could not reach the Privo server. Please check that the backend is running.",
            networkError instanceof Error ? networkError.message : null
        );
    }

    // HTTP response received. Check the status code.
    if (!response.ok) {
        // response.ok is true for status codes 200–299.
        // For 400, 422, 500, etc., response.ok is false.
        // handleErrorResponse parses the body and throws PrivoApiError.
        await handleErrorResponse(response);
        // TypeScript knows handleErrorResponse always throws (Promise<never>),
        // so execution never continues past this line on error responses.
        // No `return` or `else` needed after this call.
    }

    // Status is 200–299. Parse the success body.
    const data = await response.json() as AnalysisResponse;
    // Cast to AnalysisResponse — our typed shape for successful responses.
    // TypeScript trusts this cast. In production you could add runtime
    // validation here using a library like Zod to verify the shape,
    // but for Week 1 the cast is appropriate.

    return data;
}

// ─────────────────────────────────────────────────────────────────
// FUTURE API FUNCTIONS (not implemented yet)
// Stubs are not created — only documented here so you know
// what gets added and in which week.
// ─────────────────────────────────────────────────────────────────

// Week 2+:
// export async function getSessionStatus(
//   sessionId: string
// ): Promise<SessionStatusResponse>
//   GET /api/v1/session/{sessionId}/status

// Week 3+:
// export async function pollDetectionResult(
//   sessionId: string
// ): Promise<DetectionResponse>
//   GET /api/v1/session/{sessionId}/detection

// Week 6+:
// export async function applyProtection(
//   sessionId: string,
//   regions: ProtectionRegion[]
// ): Promise<ProtectionResponse>
//   POST /api/v1/session/{sessionId}/protect
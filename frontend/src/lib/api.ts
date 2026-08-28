/**
 * src/lib/api.ts
 *
 * PURPOSE
 * -------
 * Centralised HTTP client for all communication between the
 * React Native app and the FastAPI backend on the laptop.
 *
 * Every network call the app makes goes through this file.
 * No component or hook ever calls axios or fetch directly.
 *
 * ─────────────────────────────────────────────────────────────────
 * WHY AXIOS INSTEAD OF fetch()
 * ─────────────────────────────────────────────────────────────────
 * fetch() works in React Native but has known inconsistencies
 * with multipart/form-data on Android — specifically around
 * how the Content-Type boundary is set and how file blobs are
 * serialised. Axios handles this correctly and consistently
 * across Android versions.
 *
 * axios is already installed: package.json → "axios": "^1.20.0"
 *
 * ─────────────────────────────────────────────────────────────────
 * IMAGE FORMAT — WHY { uri, name, type } AND NOT File
 * ─────────────────────────────────────────────────────────────────
 * In a browser, expo-image-picker would give a File object.
 * In React Native, expo-image-picker gives an asset object:
 *   { uri: "file:///...", fileName: "photo.jpg", mimeType: "image/jpeg" }
 *
 * FormData in React Native accepts { uri, name, type } for file fields.
 * This is the React Native multipart file upload pattern.
 * The FastAPI backend receives it identically to a browser File upload.
 *
 * ─────────────────────────────────────────────────────────────────
 * CONNECTION
 * ─────────────────────────────────────────────────────────────────
 * URL comes from constants.ts → ENDPOINTS.ANALYZE
 * To switch USB ↔ WiFi ↔ cloud: change API_BASE_URL in constants.ts
 *
 * USB (current): adb reverse tcp:8000 tcp:8000
 *   phone → USB → laptop:8000 → FastAPI
 *
 * ─────────────────────────────────────────────────────────────────
 * HOW THIS FILE COMMUNICATES WITH OTHER MODULES
 * ─────────────────────────────────────────────────────────────────
 * Imports from:
 *   src/lib/constants.ts → ENDPOINTS, REQUEST_TIMEOUT_MS
 *   src/types/analysis.ts → AnalysisResponse, FastAPIError, ErrorCode
 *
 * Imported by:
 *   src/features/upload/useUpload.ts → calls analyzeImage()
 *
 * Future callers (added as backend weeks complete):
 *   src/features/session/useSession.ts → getSessionStatus()
 *   src/features/protection/useProtection.ts → applyProtection()
 *   src/features/gallery/useGallery.ts → getGallery()
 *
 * FUTURE API FUNCTIONS (do not add until backend week arrives)
 * ─────────────────────────────────────────────────────────────────
 * Week 5+: getSessionStatus(sessionId: string)
 *   GET /api/v1/session/{sessionId}/status
 *
 * Week 7+: applyProtection(sessionId: string, regions: ProtectionRegion[])
 *   POST /api/v1/session/{sessionId}/protect
 *
 * Week 9+: getGallery()
 *   GET /api/v1/gallery
 */

import axios, { AxiosError } from "axios";
// axios: HTTP client library
// AxiosError: typed error class for axios failures —
//   has .response (server replied), .request (no reply), .message (setup error)

import {
    ENDPOINTS,
    REQUEST_TIMEOUT_MS,
} from "./constants";

import type {
    AnalysisResponse,
    FastAPIError,
    ErrorCode,
} from "../types/analysis";
// import type: erased at compile time, zero runtime cost.
// These are only used for type annotations in this file.


// ─────────────────────────────────────────────────────────────────
// IMAGE ASSET TYPE
// The shape expo-image-picker returns for a selected image.
// ─────────────────────────────────────────────────────────────────

/**
 * Represents a selected image from expo-image-picker.
 *
 * expo-image-picker returns ImagePickerAsset objects with these fields.
 * We only use what we need for the upload — uri, fileName, mimeType.
 *
 * WHY NOT IMPORT ImagePickerAsset FROM expo-image-picker?
 * --------------------------------------------------------
 * Importing from expo-image-picker here would couple api.ts to Expo.
 * If the image source ever changes (camera capture, share intent, etc.),
 * a different source might produce a different asset shape.
 *
 * Using our own UploadableImage interface keeps api.ts source-agnostic.
 * useUpload.ts maps any image source to this shape before calling api.ts.
 * api.ts never knows or cares where the image came from.
 *
 * FUTURE EXTENSIBILITY
 * --------------------
 * On-device processing (Phase 2) may produce images differently.
 * As long as the caller provides { uri, name, type }, api.ts works.
 */
export interface UploadableImage {
    /** File URI from expo-image-picker or expo-camera. */
    uri: string;
    // Example: "file:///data/user/0/host.exp.exponent/cache/ImagePicker/photo.jpg"
    // React Native FormData uses this URI to read the file bytes.

    /** Original filename. Used as the multipart field filename. */
    name: string;
    // Example: "photo.jpg"
    // Sent to FastAPI as the filename in the multipart form field.
    // FastAPI reads this as UploadFile.filename.

    /** MIME type of the image. */
    type: string;
    // Example: "image/jpeg"
    // Sent as the Content-Type of the file part in multipart form.
}


// ─────────────────────────────────────────────────────────────────
// CUSTOM ERROR CLASS
// ─────────────────────────────────────────────────────────────────

/**
 * Typed error thrown by all api.ts functions on failure.
 *
 * WHY A CUSTOM ERROR CLASS?
 * --------------------------
 * axios throws AxiosError on failure — it has .response, .request,
 * and .message but no Privo-specific fields.
 *
 * PrivoApiError carries structured information from the backend:
 *   error.code    → "FILE_TOO_LARGE" (switch in UI for specific guidance)
 *   error.message → "File is 45 MB..." (display to user)
 *   error.status  → 400 / 500 / 0 (0 = network failure)
 *
 * HOW useUpload.ts CATCHES THIS
 * ------------------------------
 * try {
 *   const result = await analyzeImage(asset)
 * } catch (err) {
 *   if (err instanceof PrivoApiError) {
 *     setError(err.message)   // show to user
 *   }
 * }
 *
 * instanceof PrivoApiError distinguishes structured API errors
 * from unexpected JavaScript errors caught in the same block.
 */
export class PrivoApiError extends Error {
    public readonly status: number;
    public readonly code: ErrorCode;
    public readonly detail: string | null;

    constructor(
        status: number,
        code: ErrorCode,
        message: string,
        detail: string | null = null
    ) {
        super(message);
        this.name = "PrivoApiError";
        this.status = status;
        this.code = code;
        this.detail = detail;

        // Fix prototype chain for instanceof checks in TypeScript.
        // Required when extending built-in classes like Error.
        // Without this, `err instanceof PrivoApiError` can return false.
        Object.setPrototypeOf(this, PrivoApiError.prototype);
    }
}


// ─────────────────────────────────────────────────────────────────
// AXIOS INSTANCE
// Shared instance with default config applied to every request.
// ─────────────────────────────────────────────────────────────────

/**
 * Configured axios instance used for all Privo API calls.
 *
 * WHY A SHARED INSTANCE AND NOT axios.post() DIRECTLY?
 * -----------------------------------------------------
 * A shared instance with defaults means:
 * - Timeout is set once, applied everywhere
 * - Future: auth headers added here, applied to all requests
 * - Future: request interceptor for logging added once
 * - Future: response interceptor for token refresh added once
 *
 * All future API functions use this instance, not bare axios.
 */
const apiClient = axios.create({
    timeout: REQUEST_TIMEOUT_MS,
    // If the server takes longer than REQUEST_TIMEOUT_MS (30 seconds),
    // axios throws an AxiosError with code "ECONNABORTED".
    // handleAxiosError() catches this and produces a user-friendly message.

    headers: {
        Accept: "application/json",
        // Tell the server we expect JSON back.
        // Do NOT set Content-Type here — axios sets it automatically
        // per request based on the request body type.
        // For FormData uploads, axios sets:
        //   Content-Type: multipart/form-data; boundary=----...
        // Setting it here would override that and break file uploads.
    },
});


// ─────────────────────────────────────────────────────────────────
// INTERNAL HELPERS
// ─────────────────────────────────────────────────────────────────

/**
 * Converts an AxiosError into a PrivoApiError.
 *
 * THREE AXIOS ERROR CASES
 * -----------------------
 * Case 1 — Server responded with an error status (4xx, 5xx):
 *   error.response is set.
 *   We parse the FastAPI error body: { "detail": { error_code, message } }
 *   and extract the structured fields.
 *
 * Case 2 — Request was made but no response received:
 *   error.request is set, error.response is undefined.
 *   Network failure — FastAPI is not running, USB tunnel not set up,
 *   or WiFi is disconnected.
 *
 * Case 3 — Request setup failed before sending:
 *   Neither error.response nor error.request is set.
 *   Configuration error — malformed URL, invalid FormData, etc.
 *
 * WHY Promise<never>?
 * -------------------
 * This function always throws — it never returns normally.
 * Promise<never> tells TypeScript that execution never continues
 * past a call to this function. No `return` needed after the call.
 */
async function handleAxiosError(error: AxiosError): Promise<never> {
    // Case 1: Server replied with error status
    if (error.response) {
        const status = error.response.status;

        let code: ErrorCode = "VALIDATION_FAILED";
        let message = "An unexpected error occurred. Please try again.";
        let detail: string | null = null;

        try {
            // FastAPI error shape: { "detail": { success, error_code, message, detail } }
            const body = error.response.data as FastAPIError;

            if (body?.detail && typeof body.detail === "object") {
                code = body.detail.error_code ?? "VALIDATION_FAILED";
                message = body.detail.message ?? message;
                detail = body.detail.detail ?? null;
            }
        } catch {
            // Body could not be parsed as FastAPIError — use defaults above.
        }

        throw new PrivoApiError(status, code, message, detail);
    }

    // Case 2: No response received — network failure
    if (error.request) {
        // Check if this was a timeout
        if (error.code === "ECONNABORTED") {
            throw new PrivoApiError(
                0,
                "TRIGGER_ENGINE_ERROR",
                "The request timed out. The server may be processing a large image. Please try again.",
                null
            );
        }

        throw new PrivoApiError(
            0,
            "TRIGGER_ENGINE_ERROR",
            "Could not reach the Privo server. Make sure:\n" +
            "• The FastAPI backend is running on your laptop\n" +
            "• The USB cable is connected\n" +
            "• adb reverse tcp:8000 tcp:8000 has been run",
            null
        );
    }

    // Case 3: Request setup error
    throw new PrivoApiError(
        0,
        "TRIGGER_ENGINE_ERROR",
        "A request configuration error occurred. Please restart the app.",
        error.message ?? null
    );
}


// ─────────────────────────────────────────────────────────────────
// API FUNCTIONS
// ─────────────────────────────────────────────────────────────────

/**
 * Uploads an image to the Privo analysis pipeline.
 *
 * ENDPOINT
 * --------
 * POST /api/v1/analyze
 * Content-Type: multipart/form-data
 * Body field name: "file"   ← must match FastAPI parameter name exactly
 *
 * PARAMETERS
 * ----------
 * image : UploadableImage
 *   { uri, name, type } — produced by useUpload.ts from the
 *   expo-image-picker asset or expo-camera capture.
 *
 * RETURNS
 * -------
 * Promise<AnalysisResponse>
 *   Resolves with the full typed response on HTTP 200.
 *
 * THROWS
 * ------
 * PrivoApiError
 *   On any failure: validation error (400), server error (500),
 *   network failure (no response), or timeout.
 *
 * HOW FormData WORKS IN REACT NATIVE
 * ------------------------------------
 * React Native's FormData.append() accepts a special object format
 * for files — { uri, name, type } — not a File or Blob object.
 * axios serialises this using the React Native XMLHttpRequest bridge
 * which reads the file bytes from the local URI.
 *
 * The backend receives this identically to a browser file upload.
 * FastAPI's UploadFile.filename = image.name
 * FastAPI's UploadFile.content_type = image.type
 * FastAPI's await UploadFile.read() = the actual image bytes
 *
 * WHY NOT SET Content-Type MANUALLY?
 * ------------------------------------
 * axios sets Content-Type: multipart/form-data; boundary=----...
 * automatically when the body is FormData.
 * Setting it manually omits the boundary string and breaks parsing.
 * Never set Content-Type manually for FormData uploads.
 */
export async function analyzeImage(
    image: UploadableImage
): Promise<AnalysisResponse> {

    const formData = new FormData();

    formData.append("file", {
        uri: image.uri,
        name: image.name,
        type: image.type,
    } as unknown as Blob);
    // `as unknown as Blob`: TypeScript's FormData type definition
    // expects a Blob or string. React Native's runtime FormData
    // accepts { uri, name, type } objects for file uploads.
    // This cast tells TypeScript to trust us — the runtime handles it.
    // This is the standard React Native multipart upload pattern.

    try {
        const response = await apiClient.post<AnalysisResponse>(
            ENDPOINTS.ANALYZE,
            formData,
            // No Content-Type header — axios sets it automatically for FormData.
        );

        return response.data;
        // response.data: axios automatically parses the JSON body.
        // Typed as AnalysisResponse via the generic: post<AnalysisResponse>()

    } catch (error) {
        if (axios.isAxiosError(error)) {
            // axios.isAxiosError: type guard that narrows error to AxiosError.
            // Only AxiosError has .response and .request fields.
            await handleAxiosError(error);
            // handleAxiosError always throws — execution never reaches here.
            // TypeScript knows this because of Promise<never> return type.
        }

        // Non-axios error (unexpected JavaScript error).
        // Should not happen in practice — defensive handling.
        throw new PrivoApiError(
            0,
            "TRIGGER_ENGINE_ERROR",
            "An unexpected error occurred. Please restart the app.",
            error instanceof Error ? error.message : null
        );
    }
}
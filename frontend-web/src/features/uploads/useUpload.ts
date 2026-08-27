/**
 * frontend/src/features/upload/useUpload.ts
 *
 * PURPOSE
 * -------
 * Custom React hook that manages all state and logic for the
 * image upload feature.
 *
 * This hook is the "brain" of the upload feature.
 * UploadZone.tsx is the "face" — it only renders what this hook provides.
 *
 * WHY A CUSTOM HOOK?
 * ------------------
 * React components re-render whenever their state changes.
 * If you put all logic (API calls, validation, state updates) directly
 * inside a component, the component becomes large and hard to test.
 *
 * A custom hook extracts that logic into a separate function that:
 * - Can be tested without rendering any UI
 * - Can be reused by a different component in the future
 * - Keeps the component file focused on rendering only
 *
 * WHAT THIS HOOK MANAGES
 * ----------------------
 * file        → the File object selected by the user
 * previewUrl  → a temporary browser URL for showing an image preview
 * loading     → true while the API call is in progress
 * result      → the AnalysisResponse from the backend (on success)
 * error       → a human-readable error message (on failure)
 *
 * HOW THIS FILE COMMUNICATES WITH OTHER MODULES
 * ----------------------------------------------
 * Calls:
 *   src/lib/api.ts → analyzeImage(file) to send the image to FastAPI
 *
 * Imports types from:
 *   src/types/analysis.ts → AnalysisResponse, ErrorCode
 *
 * Used by:
 *   src/features/upload/UploadZone.tsx
 *     → calls useUpload() and renders the returned state and handlers
 *
 * Future callers:
 *   src/features/camera/useCamera.ts
 *     → will share the same analyzeImage() call pattern for camera frames
 *     → may share a common useAnalysis() base hook extracted from here
 */

import { useState, useCallback } from "react";
// useState: React hook for declaring stateful values.
//   const [value, setValue] = useState(initialValue)
//   - value: the current state value
//   - setValue: a function to update it
//   When setValue is called, React re-renders the component that
//   called this hook, reflecting the new value in the UI.
//
// useCallback: React hook that memoises a function.
//   const fn = useCallback(() => { ... }, [dependencies])
//   Without useCallback, a new function object is created on every render.
//   With useCallback, the same function object is reused as long as
//   the dependency array values don't change.
//
//   WHY IT MATTERS HERE:
//   handleFileSelect and handleAnalyze are passed as event handlers
//   to UploadZone. If they were recreated every render, React would
//   see them as "new" functions and potentially cause unnecessary
//   child re-renders. useCallback prevents this.

import { analyzeImage, PrivoApiError } from "../../lib/api";
// analyzeImage: The API function that sends the file to FastAPI.
//   Returns Promise<AnalysisResponse> on success.
//   Throws PrivoApiError on failure.
//
// PrivoApiError: Our custom error class from api.ts.
//   We use `instanceof PrivoApiError` to distinguish structured
//   API errors from unexpected JavaScript errors.

import type { AnalysisResponse } from "../../types/analysis";
// AnalysisResponse: TypeScript interface for the backend's success response.
//   Used as the type for the `result` state variable.
//   `import type` — erased at compile time, no runtime cost.


// ─────────────────────────────────────────────────────────────────
// HOOK RETURN TYPE
// Explicitly declaring what the hook returns makes the contract
// between useUpload and UploadZone clear and type-safe.
// ─────────────────────────────────────────────────────────────────

/**
 * The shape of the object returned by useUpload().
 *
 * WHY DECLARE THIS AS AN INTERFACE?
 * ----------------------------------
 * Without an explicit interface, TypeScript infers the return type
 * automatically. That works, but the inferred type is not named —
 * it appears in IDE tooltips as a long anonymous object type.
 *
 * With UseUploadReturn, the IDE shows:
 *   const upload = useUpload()  →  upload: UseUploadReturn
 *
 * This makes the hook's contract visible and documentable.
 * UploadZone.tsx can import this type to annotate its props if needed.
 */
export interface UseUploadReturn {
    /** The currently selected File object. null if no file selected yet. */
    file: File | null;

    /**
     * A temporary browser-generated URL for displaying the image preview.
     * Created by URL.createObjectURL(file).
     * null if no file selected.
     *
     * IMPORTANT: This URL is only valid during the current browser session.
     * It is revoked (freed from memory) when the user resets or selects
     * a new file. Never persist this URL or store it in a database.
     */
    previewUrl: string | null;

    /** True while the analyzeImage() API call is in progress. */
    loading: boolean;

    /**
     * The successful response from POST /api/v1/analyze.
     * null if no successful analysis has been completed yet.
     * Populated after a successful API call.
     */
    result: AnalysisResponse | null;

    /**
     * Human-readable error message for display in the UI.
     * null when there is no error.
     * Set when analyzeImage() throws a PrivoApiError.
     */
    error: string | null;

    /**
     * Called when the user selects a file.
     * Accepts a File object from the file input's change event.
     * Generates a preview URL and clears previous results.
     */
    handleFileSelect: (file: File) => void;

    /**
     * Called when the user clicks the Analyze button.
     * Sends the selected file to the backend and updates state
     * with the result or error.
     */
    handleAnalyze: () => Promise<void>;

    /**
     * Resets all state to its initial values.
     * Called when the user wants to start over with a new image.
     * Also revokes the preview URL to free browser memory.
     */
    handleReset: () => void;
}


// ─────────────────────────────────────────────────────────────────
// HOOK
// ─────────────────────────────────────────────────────────────────

/**
 * useUpload — manages all state and logic for the upload feature.
 *
 * USAGE IN UploadZone.tsx
 * -----------------------
 * const {
 *   file, previewUrl, loading, result, error,
 *   handleFileSelect, handleAnalyze, handleReset
 * } = useUpload()
 *
 * RULES FOR CALLING THIS HOOK
 * ----------------------------
 * Like all React hooks, useUpload must be called:
 * - At the top level of a component or another hook (never inside
 *   a loop, condition, or nested function)
 * - Only from React function components or other custom hooks
 *   (never from a plain JavaScript function)
 *
 * These rules exist because React tracks hooks by call order.
 * Calling a hook conditionally would break that ordering.
 *
 * @returns UseUploadReturn — the complete state and handler set
 */
export function useUpload(): UseUploadReturn {

    // ── STATE DECLARATIONS ────────────────────────────────────────

    const [file, setFile] = useState<File | null>(null);
    // File | null: Either a File object or null (no file selected).
    // Initial value: null (nothing selected at page load).

    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    // string | null: Either a blob URL string or null.
    // Example value: "blob:http://localhost:5173/a1b2c3d4-..."
    // This URL is created by the browser and points to the file in memory.

    const [loading, setLoading] = useState<boolean>(false);
    // boolean: true while the API call is running, false otherwise.
    // Used by UploadZone to show a loading spinner and disable the button.

    const [result, setResult] = useState<AnalysisResponse | null>(null);
    // AnalysisResponse | null: The backend response or null.
    // Populated after a successful analyzeImage() call.

    const [error, setError] = useState<string | null>(null);
    // string | null: A human-readable error message or null.
    // Populated when analyzeImage() throws a PrivoApiError.


    // ── HANDLERS ─────────────────────────────────────────────────

    /**
     * Handles file selection from the file input or drag-and-drop.
     *
     * WHAT IT DOES
     * ------------
     * 1. Stores the File object in state
     * 2. Revokes any existing preview URL (frees memory)
     * 3. Creates a new preview URL from the new file
     * 4. Clears any previous result and error (fresh start)
     *
     * WHY useCallback?
     * ----------------
     * This function is passed as a prop to UploadZone.
     * Without useCallback, a new function is created on every render,
     * which would cause UploadZone to see a "different" prop each time
     * and potentially re-render unnecessarily.
     *
     * The dependency array [] means: never recreate this function.
     * This is safe because handleFileSelect does not depend on any
     * state that would change — it only calls state setters (setFile,
     * setPreviewUrl, etc.) which are stable references from useState.
     *
     * WHY NOT ACCEPT A FileList?
     * ---------------------------
     * FileList is the raw type from event.target.files.
     * Accepting a single File forces UploadZone to extract the file
     * before calling this handler — keeping the handler simple and
     * independently testable without a DOM event.
     */
    const handleFileSelect = useCallback((selectedFile: File) => {
        // Revoke the existing preview URL before creating a new one.
        // URL.createObjectURL() allocates memory in the browser.
        // If you don't revoke it, old preview URLs accumulate in memory
        // for the lifetime of the browser tab — a memory leak.
        setPreviewUrl(prev => {
            if (prev) {
                URL.revokeObjectURL(prev);
                // URL.revokeObjectURL: Releases the memory held by the blob URL.
                // After this call, the URL is invalid and can no longer be used
                // to display the image. We're about to replace it anyway.
            }
            return null;
            // Return null temporarily — the new URL is set below.
            // We use the functional form of setPreviewUrl (prev => ...)
            // to access the current value inside the setter without adding
            // previewUrl to the useCallback dependency array.
        });

        setFile(selectedFile);
        setPreviewUrl(URL.createObjectURL(selectedFile));
        // URL.createObjectURL(file): Creates a temporary URL pointing to the
        // file's data in browser memory.
        // Example output: "blob:http://localhost:5173/a1b2c3d4-e5f6-..."
        // This can be used directly as the `src` of an <img> tag to
        // display a preview without uploading the file first.

        // Clear previous results so a fresh selection always starts clean.
        setResult(null);
        setError(null);
    }, []);
    // Dependency array []: this function never needs to be recreated.


    /**
     * Sends the selected file to the backend for analysis.
     *
     * WHAT IT DOES
     * ------------
     * 1. Guards: does nothing if no file is selected or already loading
     * 2. Sets loading=true, clears previous error
     * 3. Calls analyzeImage(file) from api.ts
     * 4. On success: stores the AnalysisResponse in result state
     * 5. On PrivoApiError: stores the error message in error state
     * 6. On unexpected error: stores a generic message in error state
     * 7. Always: sets loading=false when done
     *
     * WHY async?
     * ----------
     * analyzeImage() returns a Promise — it is an asynchronous operation
     * that takes time (network request to FastAPI). We await it so that
     * the code reads top-to-bottom without nested .then() callbacks.
     * React handles async event handlers correctly — no special setup needed.
     *
     * WHY THREE ERROR CASES?
     * ----------------------
     * Case 1: PrivoApiError — structured error from our backend.
     *   We show err.message (written by the backend to be user-friendly).
     *
     * Case 2: Any other Error — unexpected JavaScript error.
     *   Could be a JSON parse failure, a null reference, anything.
     *   We show err.message but log the full error for debugging.
     *
     * Case 3: Non-Error throw — extremely rare but JavaScript allows
     *   `throw "string"` or `throw 42`. We show a safe generic message.
     *
     * Separating these three cases means the user always sees a
     * meaningful message, and developers always see the full error in
     * the console for debugging.
     */
    const handleAnalyze = useCallback(async () => {
        // Guard: can't analyze without a file
        if (!file) return;

        // Guard: don't start a second request while one is in progress
        if (loading) return;

        setLoading(true);
        setError(null);
        // Clear any previous error before the new attempt.
        // If the user retries after an error, they should see a clean state.

        try {
            const analysisResult = await analyzeImage(file);
            // analyzeImage is imported from api.ts.
            // It builds FormData, calls fetch(), and returns AnalysisResponse.
            // It throws PrivoApiError on any failure.

            setResult(analysisResult);
            // Store the full AnalysisResponse in state.
            // UploadZone will read result and render the session details.

        } catch (err) {
            if (err instanceof PrivoApiError) {
                // Structured error from our backend.
                // err.message is written by the backend to be user-friendly.
                // err.code is available if we want to show specific guidance.
                setError(err.message);

            } else if (err instanceof Error) {
                // Unexpected JavaScript error (not from our API).
                // Log the full error for debugging, show a safe message.
                console.error("useUpload: unexpected error during analysis:", err);
                setError("Something went wrong. Please try again.");

            } else {
                // Non-Error throw — very rare but defensive handling.
                console.error("useUpload: unknown error type thrown:", err);
                setError("An unknown error occurred. Please try again.");
            }

        } finally {
            setLoading(false);
            // finally: runs whether the try block succeeded or threw.
            // This guarantees loading is always set back to false,
            // even if an error occurred. Without finally, a thrown error
            // would leave loading=true forever, disabling the analyze button.
        }
    }, [file, loading]);
    // Dependency array [file, loading]:
    // handleAnalyze depends on `file` (it's sent to the API)
    // and `loading` (used as a guard). If either changes,
    // a new version of the function is created that closes over
    // the new values. This is correct — we always want the
    // function to use the current file and current loading state.


    /**
     * Resets all state to initial values.
     *
     * WHAT IT DOES
     * ------------
     * 1. Revokes the preview URL (frees browser memory)
     * 2. Sets all state back to null/false
     *
     * WHEN TO CALL THIS
     * -----------------
     * - User clicks "Analyse Another Image"
     * - User wants to start over after seeing results
     * - Error occurred and user wants to retry with a different file
     *
     * WHY REVOKE THE URL HERE?
     * ------------------------
     * When the component unmounts (user navigates away) or the user
     * resets, the preview URL must be revoked to prevent memory leaks.
     * setPreviewUrl(null) alone does not free the memory — the
     * browser holds it until URL.revokeObjectURL() is called.
     */
    const handleReset = useCallback(() => {
        if (previewUrl) {
            URL.revokeObjectURL(previewUrl);
        }
        setFile(null);
        setPreviewUrl(null);
        setLoading(false);
        setResult(null);
        setError(null);
    }, [previewUrl]);
    // Dependency array [previewUrl]:
    // handleReset needs the current previewUrl to revoke it.
    // When previewUrl changes (new file selected), a new version
    // of handleReset is created that holds the new URL.


    // ── RETURN ───────────────────────────────────────────────────

    return {
        file,
        previewUrl,
        loading,
        result,
        error,
        handleFileSelect,
        handleAnalyze,
        handleReset,
    };
    // The hook returns a plain object with state values and handlers.
    // UploadZone destructures this:
    //   const { file, previewUrl, loading, result, error,
    //           handleFileSelect, handleAnalyze, handleReset } = useUpload()
    //
    // WHY NOT RETURN AN ARRAY LIKE useState?
    // ----------------------------------------
    // useState returns [value, setter] — a two-item array where the
    // order matters: const [count, setCount] = useState(0).
    // This works for single values because there are only two items.
    //
    // Custom hooks return objects when there are many values.
    // An object lets the caller destructure by name:
    //   const { loading, error } = useUpload()
    // vs an array where order must be memorised:
    //   const [,,loading,,,error] = useUpload()  ← unreadable
}
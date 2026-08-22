/**
 * frontend/src/features/upload/UploadZone.tsx
 *
 * PURPOSE
 * -------
 * The upload feature component. Renders the complete upload UI:
 * file selection, image preview, Analyze button, loading state,
 * result display, and error handling.
 *
 * This component contains zero logic.
 * All state and behaviour comes from useUpload().
 * This component only renders what the hook provides.
 *
 * WHY ZERO LOGIC IN THE COMPONENT?
 * ---------------------------------
 * Separating rendering (this file) from logic (useUpload.ts) means:
 * - The hook is testable without a browser or DOM
 * - The component is readable — it describes the UI, not the behaviour
 * - If the visual design changes completely, the hook does not change
 * - If the API changes, the hook changes but the JSX structure stays
 *
 * WHAT THIS COMPONENT RENDERS
 * ----------------------------
 * State 1 — No file selected:
 *   Empty drop zone with "Select Image" button and format hint
 *
 * State 2 — File selected, not yet analysed:
 *   Image preview + filename + file size + "Analyse Image" button
 *
 * State 3 — Loading (API call in progress):
 *   Disabled button with spinner + "Analysing..." text
 *
 * State 4 — Result received:
 *   Session ID, source, status, settings panel, raw JSON view
 *
 * State 5 — Error:
 *   Error message + "Try Again" button
 *
 * HOW THIS FILE COMMUNICATES WITH OTHER MODULES
 * ----------------------------------------------
 * Calls:
 *   src/features/upload/useUpload.ts → useUpload()
 *     Provides all state and handlers.
 *
 * Imports types from:
 *   src/types/analysis.ts → AnalysisResponse, SettingsSnapshot
 *     Used as prop types for sub-components.
 *
 * Used by:
 *   src/App.tsx → renders <UploadZone /> directly in Week 1
 *   Future: src/pages/AnalyzePage.tsx
 */

import { useRef } from "react";
// useRef: React hook that creates a mutable reference object.
// Here we use it to hold a reference to the hidden <input type="file"> element.
// This lets us trigger the native file picker dialog programmatically
// when the user clicks our styled button — without exposing the
// ugly default browser file input.
//
// WHY useRef AND NOT useState?
// ----------------------------
// useRef stores a value that:
// - Persists across renders (like state)
// - Does NOT trigger a re-render when changed (unlike state)
// DOM references should always be useRef, never useState.
// Storing a DOM node in state would cause unnecessary re-renders
// every time the component renders and the ref is set.

import { useUpload } from "./useUpload";
// useUpload: Our custom hook from the same feature folder.
// Provides all state values and event handlers.
// Keeps this component free of any logic.

import type { AnalysisResponse, SettingsSnapshot } from "../../types/analysis";
// AnalysisResponse: Type for the result prop on ResultPanel.
// SettingsSnapshot: Type for the settings prop on SettingsPanel.
// import type: erased at compile time, no runtime cost.


// ─────────────────────────────────────────────────────────────────
// HELPER: FORMAT FILE SIZE
// Converts raw bytes to a human-readable string.
// Example: 2457600 → "2.3 MB"
// ─────────────────────────────────────────────────────────────────

/**
 * Converts a byte count to a human-readable file size string.
 *
 * WHY HERE AND NOT IN utils.ts?
 * ------------------------------
 * utils.ts is for helpers shared across two or more features.
 * This helper is only used inside this component right now.
 * It stays here until a second feature needs it — then it moves.
 * This follows the "shared threshold is two" rule from our directory
 * structure plan.
 */
function formatBytes(bytes: number | null): string {
    if (bytes === null) return "Unknown size";
    if (bytes === 0) return "0 B";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}


// ─────────────────────────────────────────────────────────────────
// SUB-COMPONENTS
// Small, focused components extracted to keep the main component
// readable. Each sub-component renders one specific UI section.
// ─────────────────────────────────────────────────────────────────

/**
 * Renders one row in the result details panel.
 * Label on the left, value on the right.
 */
function DetailRow({ label, value }: { label: string; value: string }) {
    return (
        <div className="flex justify-between items-center py-2 border-b border-white/10 last:border-0">
            <span className="text-sm text-slate-400">{label}</span>
            <span className="text-sm font-mono text-slate-200">{value}</span>
        </div>
    );
}
// WHY A SUB-COMPONENT FOR SOMETHING THIS SMALL?
// Each detail row has the same layout. Without this component,
// the ResultPanel would repeat the same div+span+span pattern
// five times. Extracting it makes ResultPanel read as a list
// of meaningful labels and values, not a wall of div soup.


/**
 * Renders the session settings returned from the backend.
 * Shows each setting as a labelled badge.
 */
function SettingsPanel({ settings }: { settings: SettingsSnapshot }) {
    // WHY TYPED PROP?
    // Without the SettingsSnapshot type, TypeScript treats settings as `any`.
    // Accessing settings.scanning_mode would not be type-checked.
    // With the type, a typo like settings.scanningMode is a compile error.

    return (
        <div className="mt-4 pt-4 border-t border-white/10">
            <p className="text-xs uppercase tracking-widest text-slate-500 mb-3">
                Session Settings
            </p>
            <div className="flex flex-wrap gap-2">
                {/* Scanning mode badge */}
                <span className="px-2 py-1 rounded-md bg-violet-500/20 text-violet-300 text-xs font-mono">
                    {settings.scanning_mode}
                </span>

                {/* Theme badge */}
                <span className="px-2 py-1 rounded-md bg-slate-700 text-slate-300 text-xs font-mono">
                    theme: {settings.theme}
                </span>

                {/* Boolean setting badges */}
                {settings.metadata_retention && (
                    <span className="px-2 py-1 rounded-md bg-emerald-500/20 text-emerald-300 text-xs font-mono">
                        metadata on
                    </span>
                )}
                {settings.analysis_history && (
                    <span className="px-2 py-1 rounded-md bg-emerald-500/20 text-emerald-300 text-xs font-mono">
                        history on
                    </span>
                )}
                {settings.cloud_processing && (
                    <span className="px-2 py-1 rounded-md bg-amber-500/20 text-amber-300 text-xs font-mono">
                        cloud on
                    </span>
                )}
                {!settings.cloud_processing && (
                    <span className="px-2 py-1 rounded-md bg-slate-700 text-slate-400 text-xs font-mono">
                        local only
                    </span>
                )}
            </div>
        </div>
    );
}


/**
 * Renders the full result panel after a successful analysis.
 * Shows session details, pipeline status, and settings.
 */
function ResultPanel({ result }: { result: AnalysisResponse }) {
    return (
        <div className="mt-6 rounded-xl border border-violet-500/30 bg-slate-900/60 overflow-hidden">

            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 bg-violet-500/10 border-b border-violet-500/20">
                <div className="flex items-center gap-2">
                    {/* Green dot — pipeline ready indicator */}
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                    <span className="text-sm font-medium text-slate-200">
                        Pipeline Ready
                    </span>
                </div>
                <span className="text-xs font-mono text-violet-400">
                    {result.status.toUpperCase()}
                </span>
            </div>

            {/* Session details */}
            <div className="px-4 py-3">
                <DetailRow label="Session ID" value={result.session_id} />
                <DetailRow label="Source" value={result.source} />
                <DetailRow label="File" value={result.filename ?? "—"} />
                {/* ?? "—": If filename is null (camera frame), show a dash */}
                <DetailRow label="Size" value={formatBytes(result.file_size_bytes)} />
                <DetailRow
                    label="Settings loaded"
                    value={result.settings_loaded ? "Yes" : "No"}
                />

                {/* Settings breakdown */}
                <SettingsPanel settings={result.settings} />
            </div>

            {/* Message from backend */}
            <div className="px-4 py-3 bg-slate-900/40 border-t border-white/10">
                <p className="text-xs text-slate-400">{result.message}</p>
            </div>

        </div>
    );
}


// ─────────────────────────────────────────────────────────────────
// MAIN COMPONENT
// ─────────────────────────────────────────────────────────────────

/**
 * UploadZone — the complete upload feature UI.
 *
 * This component takes no props.
 * All state and behaviour comes from useUpload().
 *
 * WEEK 1 RENDERING RESPONSIBILITIES
 * ----------------------------------
 * - File picker trigger (hidden input + styled button)
 * - Image preview (before analysis)
 * - Analyze button (with loading state)
 * - Result panel (after successful analysis)
 * - Error display (on failure)
 * - Reset control (to start over)
 */
export function UploadZone() {
    const {
        file,
        previewUrl,
        loading,
        result,
        error,
        handleFileSelect,
        handleAnalyze,
        handleReset,
    } = useUpload();
    // Destructure everything from the hook.
    // The component never calls useState, fetch, or any async function.
    // It only reads values and calls the handlers useUpload provides.

    // ── FILE INPUT REF ────────────────────────────────────────────
    const fileInputRef = useRef<HTMLInputElement>(null);
    // useRef<HTMLInputElement>(null): Creates a ref typed to an HTMLInputElement.
    // We attach this to the hidden <input type="file"> below.
    // When the user clicks our styled button, we call:
    //   fileInputRef.current?.click()
    // This triggers the native file picker without showing the default input.
    //
    // WHY HIDE THE DEFAULT INPUT?
    // The browser's default file input is styled by the OS and cannot be
    // customised with CSS. We hide it and trigger it programmatically
    // from a fully styled button we control.


    // ── FILE CHANGE HANDLER ───────────────────────────────────────
    const onFileInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        // React.ChangeEvent<HTMLInputElement>: The typed event object
        // for change events on an HTML input element.
        // event.target.files: A FileList — the collection of selected files.

        const selected = event.target.files?.[0];
        // event.target.files?.[0]:
        //   event.target.files  → the FileList (may be null if no files)
        //   ?.                  → optional chaining: skip if null
        //   [0]                 → first file (we only allow single selection)
        //
        // Result: the first selected File, or undefined if nothing was selected.

        if (selected) {
            handleFileSelect(selected);
            // Pass the File object to the hook's handler.
            // The hook generates the preview URL and updates state.
        }

        // Reset the input value so selecting the same file again fires onChange.
        // Without this, if the user selects photo.jpg, resets, and selects
        // photo.jpg again, the browser sees no change and onChange never fires.
        event.target.value = "";
    };


    // ── JSX ───────────────────────────────────────────────────────
    return (
        <div className="w-full max-w-lg mx-auto px-4 py-8">

            {/* ── APP HEADER ──────────────────────────────────────── */}
            <div className="mb-8 text-center">
                <h1 className="text-2xl font-bold tracking-tight text-slate-100">
                    Privo
                </h1>
                <p className="mt-1 text-sm text-slate-400">
                    Privacy Intelligence Assistant
                </p>
            </div>

            {/* ── HIDDEN FILE INPUT ───────────────────────────────── */}
            {/*
        This input is visually hidden but functionally active.
        We trigger it programmatically from the button below.

        accept: restricts the file picker dialog to image formats.
        Matches settings.allowed_extensions on the backend.
        Note: the user can still manually type a path to any file —
        the backend Trigger Engine does the real validation.
      */}
            <input
                ref={fileInputRef}
                type="file"
                accept=".jpg,.jpeg,.png,.webp,.heic,.heif"
                onChange={onFileInputChange}
                className="hidden"
                aria-hidden="true"
            // aria-hidden: tells screen readers to ignore this element.
            // The visible button below is the accessible control point.
            />

            {/* ── UPLOAD CARD ─────────────────────────────────────── */}
            <div className="rounded-2xl border border-white/10 bg-slate-900/80 backdrop-blur-sm overflow-hidden">

                {/* ── STATE 1: NO FILE SELECTED ─────────────────────── */}
                {!file && (
                    <div className="flex flex-col items-center justify-center px-8 py-14 gap-5">

                        {/* Shield icon — privacy theme */}
                        <div className="w-16 h-16 rounded-2xl bg-violet-500/15 flex items-center justify-center">
                            <svg
                                className="w-8 h-8 text-violet-400"
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                                strokeWidth={1.5}
                                aria-hidden="true"
                            >
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959
                     11.959 0 013.598 6 11.99 11.99 0 003 9.749c0
                     5.592 3.824 10.29 9 11.623 5.176-1.332
                     9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196
                     0-6.1-1.248-8.25-3.285z"
                                />
                            </svg>
                        </div>

                        <div className="text-center">
                            <p className="text-slate-300 font-medium">
                                Select an image to analyse
                            </p>
                            <p className="mt-1 text-xs text-slate-500">
                                JPG, PNG, WebP, HEIC · up to 20 MB
                            </p>
                        </div>

                        <button
                            onClick={() => fileInputRef.current?.click()}
                            // fileInputRef.current?.click():
                            //   fileInputRef.current → the actual DOM input element
                            //   ?.                   → optional chaining (null-safe)
                            //   .click()             → triggers the native file picker
                            className="px-5 py-2.5 rounded-lg bg-violet-600 hover:bg-violet-500
                         active:bg-violet-700 text-white text-sm font-medium
                         transition-colors duration-150 focus:outline-none
                         focus:ring-2 focus:ring-violet-500 focus:ring-offset-2
                         focus:ring-offset-slate-900"
                        >
                            Select Image
                        </button>
                    </div>
                )}

                {/* ── STATE 2 & 3: FILE SELECTED ────────────────────── */}
                {file && (
                    <div className="flex flex-col gap-0">

                        {/* Image preview */}
                        {previewUrl && (
                            <div className="relative w-full aspect-video bg-slate-950 overflow-hidden">
                                {/*
                  aspect-video: maintains 16:9 ratio regardless of image.
                  This keeps the layout stable — no content jump as the
                  image loads or as state changes.
                */}
                                <img
                                    src={previewUrl}
                                    alt="Selected image preview"
                                    className="w-full h-full object-contain"
                                // object-contain: shows the full image without cropping,
                                // letterboxing if needed. object-cover would crop to fill.
                                />
                            </div>
                        )}

                        {/* File info + actions */}
                        <div className="px-5 py-4 flex flex-col gap-4">

                            {/* File metadata row */}
                            <div className="flex items-center justify-between">
                                <div className="min-w-0">
                                    {/* min-w-0: allows the flex child to shrink below its content size,
                      enabling text-ellipsis truncation to work correctly */}
                                    <p className="text-sm font-medium text-slate-200 truncate">
                                        {file.name}
                                    </p>
                                    <p className="text-xs text-slate-500 mt-0.5">
                                        {formatBytes(file.size)}
                                    </p>
                                </div>

                                {/* Reset button — only shown when not loading */}
                                {!loading && (
                                    <button
                                        onClick={handleReset}
                                        className="ml-4 flex-shrink-0 text-xs text-slate-500
                               hover:text-slate-300 transition-colors duration-150
                               focus:outline-none focus:underline"
                                        aria-label="Remove selected image and start over"
                                    >
                                        Remove
                                    </button>
                                )}
                            </div>

                            {/* Analyze button */}
                            <button
                                onClick={handleAnalyze}
                                disabled={loading}
                                // disabled: prevents clicks during the API call.
                                // Also changes the visual style via Tailwind's disabled: variant.
                                className="w-full py-3 rounded-lg text-sm font-semibold
                           transition-all duration-150 focus:outline-none
                           focus:ring-2 focus:ring-violet-500 focus:ring-offset-2
                           focus:ring-offset-slate-900
                           disabled:cursor-not-allowed disabled:opacity-60
                           bg-violet-600 hover:bg-violet-500 active:bg-violet-700
                           text-white"
                                aria-busy={loading}
                            // aria-busy: tells screen readers the button is processing.
                            // Screen readers will announce "busy" to visually-impaired users.
                            >
                                {loading ? (
                                    // Loading state — spinner + text
                                    <span className="flex items-center justify-center gap-2">
                                        <svg
                                            className="w-4 h-4 animate-spin"
                                            // animate-spin: Tailwind's built-in spinning animation.
                                            viewBox="0 0 24 24"
                                            fill="none"
                                            aria-hidden="true"
                                        >
                                            <circle
                                                className="opacity-25"
                                                cx="12" cy="12" r="10"
                                                stroke="currentColor"
                                                strokeWidth="4"
                                            />
                                            <path
                                                className="opacity-75"
                                                fill="currentColor"
                                                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                                            />
                                        </svg>
                                        Analysing...
                                    </span>
                                ) : (
                                    "Analyse Image"
                                )}
                                {/*
                  Ternary operator: condition ? ifTrue : ifFalse
                  loading === true  → show spinner + "Analysing..."
                  loading === false → show "Analyse Image"
                  React re-renders the button content whenever loading changes.
                */}
                            </button>
                        </div>
                    </div>
                )}
            </div>

            {/* ── STATE 4: ERROR ──────────────────────────────────────── */}
            {error && (
                <div
                    className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10
                     px-4 py-3 flex items-start gap-3"
                    role="alert"
                // role="alert": ARIA landmark that causes screen readers to
                // announce this content immediately when it appears.
                >
                    {/* Error icon */}
                    <svg
                        className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                        aria-hidden="true"
                    >
                        <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0
                 0118 0zm-9 3.75h.008v.008H12v-.008z"
                        />
                    </svg>
                    <p className="text-sm text-red-300 leading-relaxed">{error}</p>
                </div>
            )}
            {/*
        {error && ( ... )}
        This is React's short-circuit rendering.
        If error is null  → the && stops, nothing renders.
        If error is a string → the && continues, the div renders.
        Equivalent to: if (error !== null) return <div>...</div>
        but written inline in JSX.
      */}

            {/* ── STATE 5: RESULT ─────────────────────────────────────── */}
            {result && <ResultPanel result={result} />}
            {/*
        {result && <ResultPanel result={result} />}
        Same short-circuit pattern.
        If result is null → nothing renders.
        If result is an AnalysisResponse → ResultPanel renders.
        TypeScript knows result is AnalysisResponse here (not null)
        because the && guarantees it's truthy before the right side runs.
      */}

            {/* ── ANALYSE ANOTHER — shown after result ────────────────── */}
            {result && !loading && (
                <div className="mt-4 text-center">
                    <button
                        onClick={handleReset}
                        className="text-sm text-slate-400 hover:text-slate-200
                       transition-colors duration-150 focus:outline-none
                       focus:underline"
                    >
                        Analyse another image
                    </button>
                </div>
            )}

        </div>
    );
}
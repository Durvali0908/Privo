/**
 * src/features/upload/useUpload.ts
 *
 * PURPOSE
 * -------
 * Custom hook that manages all state and logic for the image
 * upload feature. This is the "brain" of the upload screen.
 *
 * UploadZone.tsx is the "face" — it only renders what this hook returns.
 * This hook contains zero JSX and zero React Native UI imports.
 *
 * ─────────────────────────────────────────────────────────────────
 * DIFFERENCES FROM THE WEB VERSION
 * ─────────────────────────────────────────────────────────────────
 * Web version used:
 *   - Browser File object from <input type="file">
 *   - URL.createObjectURL(file) for image preview
 *   - fetch() via api.ts
 *
 * React Native version uses:
 *   - expo-image-picker → ImagePickerAsset (has .uri, .fileName, .mimeType)
 *   - asset.uri directly for image preview (no createObjectURL needed)
 *   - axios via api.ts (UploadableImage shape)
 *
 * The state management structure is identical:
 *   file, previewUri, loading, result, error
 *   handlePickImage, handleAnalyze, handleReset
 * Only the file picking mechanism and preview URL generation change.
 *
 * ─────────────────────────────────────────────────────────────────
 * HOW expo-image-picker WORKS
 * ─────────────────────────────────────────────────────────────────
 * expo-image-picker.launchImageLibraryAsync() opens the Android
 * gallery picker. When the user selects an image it returns:
 *
 *   {
 *     canceled: false,
 *     assets: [{
 *       uri:      "file:///data/user/.../photo.jpg",
 *       fileName: "photo.jpg",
 *       mimeType: "image/jpeg",
 *       width:    3024,
 *       height:   4032,
 *       fileSize: 2457600,
 *     }]
 *   }
 *
 * We read assets[0] and convert it to UploadableImage for api.ts.
 * The uri is used directly as the preview image source — React Native
 * can display local file:// URIs in <Image> without any conversion.
 *
 * ─────────────────────────────────────────────────────────────────
 * PERMISSIONS
 * ─────────────────────────────────────────────────────────────────
 * Android requires MEDIA_LIBRARY permission to access the gallery.
 * expo-image-picker.requestMediaLibraryPermissionsAsync() handles this.
 * On first use, Android shows the system permission dialog.
 * If denied, handlePickImage shows an error message.
 *
 * ─────────────────────────────────────────────────────────────────
 * HOW THIS FILE COMMUNICATES WITH OTHER MODULES
 * ─────────────────────────────────────────────────────────────────
 * Calls:
 *   expo-image-picker → opens gallery picker, requests permissions
 *   src/lib/api.ts    → analyzeImage(uploadableImage)
 *   src/lib/utils.ts  → formatBytes (for file size display)
 *
 * Imports types from:
 *   src/types/analysis.ts  → AnalysisResponse
 *   src/lib/api.ts         → UploadableImage, PrivoApiError
 *   src/lib/constants.ts   → MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_LABEL
 *
 * Used by:
 *   src/features/upload/UploadZone.tsx → calls useUpload(), renders state
 *
 * Future callers:
 *   src/features/camera/useCamera.ts
 *     → will call analyzeImage() with camera capture URI using the
 *       same UploadableImage shape — api.ts requires no changes
 */

import { useState, useCallback } from "react";
import * as ImagePicker from "expo-image-picker";
// expo-image-picker: Expo library for accessing the device gallery
// and camera roll. Already installed in package.json.
//
// We import as a namespace (* as ImagePicker) rather than named imports
// so the usage is clear: ImagePicker.launchImageLibraryAsync(),
// ImagePicker.requestMediaLibraryPermissionsAsync(), etc.

import { analyzeImage, PrivoApiError, UploadableImage } from "../../lib/api";
import type { AnalysisResponse } from "../../types/analysis";
import {
    MAX_FILE_SIZE_BYTES,
    MAX_FILE_SIZE_LABEL,
} from "../../lib/constants";


// ─────────────────────────────────────────────────────────────────
// HOOK RETURN TYPE
// ─────────────────────────────────────────────────────────────────

/**
 * Everything UploadZone.tsx receives from useUpload().
 *
 * WHY A NAMED INTERFACE?
 * ----------------------
 * Without a named return type, TypeScript infers it as an anonymous
 * object type. A named interface appears in IDE tooltips clearly:
 *   const upload = useUpload()  →  upload: UseUploadReturn
 *
 * UploadZone.tsx can also import this type if it needs to
 * pass parts of the upload state to child components as props.
 */
export interface UseUploadReturn {
    /** Selected image asset from the gallery. null if none selected. */
    asset: ImagePicker.ImagePickerAsset | null;

    /**
     * URI for displaying the image preview.
     * Comes directly from asset.uri — React Native <Image> renders
     * local file:// URIs without any conversion needed.
     * null when no image is selected.
     */
    previewUri: string | null;

    /**
     * Human-readable file size string.
     * Example: "2.3 MB"
     * null when no image is selected or size is unknown.
     */
    fileSizeLabel: string | null;

    /** True while the API request is in progress. */
    loading: boolean;

    /**
     * The successful AnalysisResponse from the backend.
     * null until a successful analysis completes.
     */
    result: AnalysisResponse | null;

    /**
     * Human-readable error message for display.
     * null when there is no error.
     */
    error: string | null;

    /**
     * Opens the Android gallery picker.
     * Requests MEDIA_LIBRARY permission if not already granted.
     * Sets asset, previewUri, and fileSizeLabel on selection.
     * Clears any previous result and error.
     */
    handlePickImage: () => Promise<void>;

    /**
     * Sends the selected image to the backend for analysis.
     * Sets loading=true, calls analyzeImage(), then sets result or error.
     * Does nothing if no image is selected or a request is in progress.
     */
    handleAnalyze: () => Promise<void>;

    /**
     * Resets all state to initial values.
     * Called when the user wants to analyse a different image.
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
 *   asset, previewUri, fileSizeLabel,
 *   loading, result, error,
 *   handlePickImage, handleAnalyze, handleReset,
 * } = useUpload()
 */
export function useUpload(): UseUploadReturn {

    // ── STATE ────────────────────────────────────────────────────
    const [asset, setAsset] = useState<ImagePicker.ImagePickerAsset | null>(null);
    // The full ImagePickerAsset from expo-image-picker.
    // We store the full asset (not just URI) so we can access
    // fileName, mimeType, fileSize, width, height when needed.

    const [previewUri, setPreviewUri] = useState<string | null>(null);
    // The URI used by <Image source={{ uri: previewUri }} />.
    // Comes from asset.uri — a local file:// path.
    // React Native renders this without any createObjectURL conversion.

    const [fileSizeLabel, setFileSizeLabel] = useState<string | null>(null);
    // Human-readable size: "2.3 MB"
    // Computed from asset.fileSize using formatBytes().
    // Displayed below the image preview.

    const [loading, setLoading] = useState<boolean>(false);
    // True while the axios request is in progress.
    // Disables the Analyse button and shows a spinner.

    const [result, setResult] = useState<AnalysisResponse | null>(null);
    // The full AnalysisResponse from the backend.
    // Populated on successful API response.

    const [error, setError] = useState<string | null>(null);
    // Human-readable error message.
    // Populated when the API call fails or validation fails client-side.


    // ── HANDLERS ─────────────────────────────────────────────────

    /**
     * Opens the Android gallery picker and handles the result.
     *
     * STEPS
     * -----
     * 1. Request MEDIA_LIBRARY permission (Android requires this)
     * 2. If denied, set error and return
     * 3. Launch the image library picker
     * 4. If canceled, do nothing
     * 5. Validate file size client-side before allowing selection
     * 6. Set asset, previewUri, fileSizeLabel
     * 7. Clear any previous result and error
     *
     * WHY CLIENT-SIDE SIZE VALIDATION?
     * ----------------------------------
     * The backend validates size too, but checking here saves a
     * network round-trip and gives the user an instant error
     * instead of waiting for the upload to fail after 10+ seconds.
     */
    const handlePickImage = useCallback(async () => {
        // Step 1: Request permission
        const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
        // requestMediaLibraryPermissionsAsync():
        //   First call → shows Android system permission dialog
        //   Subsequent calls → returns cached permission status
        //   Returns: { status: "granted" | "denied" | "undetermined" }

        // Step 2: Check permission
        if (status !== "granted") {
            setError(
                "Gallery access was denied. Please enable photo access for Privo " +
                "in your Android Settings → Apps → Privo → Permissions."
            );
            return;
        }

        // Step 3: Launch picker
        const pickerResult = await ImagePicker.launchImageLibraryAsync({
            mediaTypes: ImagePicker.MediaTypeOptions.Images,
            // MediaTypeOptions.Images: show only photos, not videos.

            allowsEditing: false,
            // allowsEditing: false — we do not want the user to crop/rotate
            // before Privo analyses the image. The full original image must
            // be sent to preserve all EXIF metadata in its original state.
            // Cropping or editing can strip metadata before analysis.

            quality: 1,
            // quality: 1 — full quality, no compression.
            // We need the original image for accurate metadata extraction.
            // Compression would degrade EXIF accuracy and lose some tags.

            exif: false,
            // exif: false — we do not need expo-image-picker to parse EXIF.
            // Privo's backend (ExifTool) handles EXIF extraction.
            // Setting false avoids unnecessary processing in the picker.
        });

        // Step 4: Check if canceled
        if (pickerResult.canceled) {
            // User pressed back or dismissed the picker.
            // Do nothing — preserve any previously selected image.
            return;
        }

        const selectedAsset = pickerResult.assets[0];
        // assets[0]: the first (and only) selected image.
        // We use allowsMultipleSelection: false (default), so assets
        // always has exactly one item when canceled is false.

        // Step 5: Client-side file size validation
        if (
            selectedAsset.fileSize &&
            selectedAsset.fileSize > MAX_FILE_SIZE_BYTES
        ) {
            // fileSize may be undefined on some Android versions.
            // Only validate if the value is available.
            setError(
                `This image is too large for Privo. ` +
                `Maximum size is ${MAX_FILE_SIZE_LABEL}. ` +
                `Try selecting a compressed version.`
            );
            return;
        }

        // Step 6: Update state with the selected image
        setAsset(selectedAsset);
        setPreviewUri(selectedAsset.uri);
        // selectedAsset.uri: local file:// path to the image.
        // Example: "file:///data/user/0/.../ImagePicker/photo.jpg"
        // React Native <Image source={{ uri }} /> renders this directly.

        // Compute human-readable file size
        if (selectedAsset.fileSize) {
            const mb = (selectedAsset.fileSize / (1024 * 1024)).toFixed(1);
            setFileSizeLabel(`${mb} MB`);
        } else {
            setFileSizeLabel(null);
        }

        // Step 7: Clear previous session state
        setResult(null);
        setError(null);

    }, []);
    // Dependency array []: handlePickImage does not close over
    // any state values — it only calls state setters which are
    // stable references. Safe to memoize with empty deps.


    /**
     * Sends the selected image to the backend for analysis.
     *
     * STEPS
     * -----
     * 1. Guard: return if no image selected or already loading
     * 2. Build UploadableImage from the asset
     * 3. Set loading=true, clear previous error
     * 4. Call analyzeImage() from api.ts
     * 5. On success: set result
     * 6. On PrivoApiError: set error message from backend
     * 7. On unexpected error: set generic error message
     * 8. Always: set loading=false (finally block)
     */
    const handleAnalyze = useCallback(async () => {
        // Step 1: Guards
        if (!asset) return;
        if (loading) return;

        // Step 2: Build UploadableImage
        // Map expo-image-picker asset → UploadableImage for api.ts.
        // api.ts is source-agnostic — it only knows UploadableImage.
        const uploadableImage: UploadableImage = {
            uri: asset.uri,
            name: asset.fileName ?? `photo_${Date.now()}.jpg`,
            // asset.fileName may be null on some Android versions.
            // Fallback: generate a timestamped filename.
            // FastAPI reads this as UploadFile.filename.

            type: asset.mimeType ?? "image/jpeg",
            // asset.mimeType may be null on some Android versions.
            // Fallback: assume JPEG — the most common format from
            // Android gallery. FastAPI uses this as Content-Type of the part.
        };

        // Step 3: Set loading state
        setLoading(true);
        setError(null);

        try {
            // Step 4: Call the API
            const analysisResult = await analyzeImage(uploadableImage);

            // Step 5: Success
            setResult(analysisResult);

        } catch (err) {
            // Step 6: PrivoApiError — structured error from backend
            if (err instanceof PrivoApiError) {
                setError(err.message);
                // err.message is written by the backend to be user-friendly.
                // err.code is available if we need to show specific guidance:
                //   if (err.code === "FILE_TOO_LARGE") { ... }

                // Step 7: Unexpected error
            } else if (err instanceof Error) {
                console.error("useUpload: unexpected error:", err);
                setError("Something went wrong. Please try again.");

            } else {
                console.error("useUpload: unknown error type:", err);
                setError("An unknown error occurred. Please restart the app.");
            }

        } finally {
            // Step 8: Always reset loading
            // finally runs whether try succeeded or catch ran.
            // Without this, loading stays true forever after any error,
            // permanently disabling the Analyse button.
            setLoading(false);
        }

    }, [asset, loading]);
    // Dependency array [asset, loading]:
    // handleAnalyze uses asset (sent to API) and loading (guard check).
    // Recreated when either changes — always closes over current values.


    /**
     * Resets all state to initial values.
     * Called when the user taps "Analyse Another Image".
     *
     * Unlike the web version, we do not need to call
     * URL.revokeObjectURL() — React Native does not allocate
     * blob URLs. The local file:// URI is managed by the OS.
     */
    const handleReset = useCallback(() => {
        setAsset(null);
        setPreviewUri(null);
        setFileSizeLabel(null);
        setLoading(false);
        setResult(null);
        setError(null);
    }, []);
    // Dependency array []: handleReset only calls state setters.
    // Stable — never needs to be recreated.


    // ── RETURN ───────────────────────────────────────────────────
    return {
        asset,
        previewUri,
        fileSizeLabel,
        loading,
        result,
        error,
        handlePickImage,
        handleAnalyze,
        handleReset,
    };
}
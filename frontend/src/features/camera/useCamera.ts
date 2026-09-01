// /**
//  * src/features/camera/useCamera.ts
//  *
//  * Manages camera permissions, capture state, and analysis
//  * for the camera screen. Produces an UploadableImage from
//  * a captured photo and passes it to analyzeImage() in api.ts.
//  *
//  * The camera flow:
//  *   1. Request camera permission
//  *   2. Show live viewfinder (CameraView renders this)
//  *   3. User taps capture → photo saved to temp URI
//  *   4. Viewfinder freezes — show captured frame
//  *   5. Send to FastAPI via analyzeImage()
//  *   6. Display results
//  *   7. User retakes or proceeds to protection
//  */

// import { useState, useCallback, useRef } from "react";
// import { CameraView, CameraType, useCameraPermissions } from "expo-camera";
// // CameraView:          expo-camera component ref type — used to call takePictureAsync()
// // CameraType:          "front" | "back"
// // useCameraPermissions: hook that returns [permission, requestPermission]

// import { analyzeImage, PrivoApiError, UploadableImage } from "../../lib/api";
// import type { AnalysisResponse } from "../../types/analysis";


// export type CameraScreenState =
//     | "permissions"    // waiting for / requesting camera permission
//     | "viewfinder"     // live camera preview active
//     | "captured"       // photo taken, frozen preview shown
//     | "analysing"      // API call in progress
//     | "result"         // analysis complete
//     | "error";         // something went wrong


// export interface UseCameraReturn {
//     /** Current screen state — drives which UI CameraView renders. */
//     screenState: CameraScreenState;

//     /** Camera facing direction. */
//     facing: CameraType;

//     /** URI of the captured photo. Set after capture, null before. */
//     capturedUri: string | null;

//     /** Analysis result from backend. */
//     result: AnalysisResponse | null;

//     /** Error message for display. */
//     error: string | null;

//     /** Ref passed to <CameraView> so we can call takePictureAsync(). */
//     cameraRef: React.RefObject<CameraView | null>;

//     /** Whether camera permission has been granted. */
//     hasPermission: boolean;

//     /** Request camera permission (called on "permissions" screen). */
//     requestPermission: () => Promise<void>;

//     /** Flip between front and back camera. */
//     handleFlipCamera: () => void;

//     /** Capture a photo. */
//     handleCapture: () => Promise<void>;

//     /** Discard captured photo — return to viewfinder. */
//     handleRetake: () => void;

//     /** Send captured photo to backend for analysis. */
//     handleAnalyze: () => Promise<void>;

//     /** Reset everything — return to viewfinder. */
//     handleReset: () => void;
// }


// export function useCamera(): UseCameraReturn {
//     const [permission, requestPermissionAsync] = useCameraPermissions();
//     const cameraRef = useRef<CameraView | null>(null);

//     const [facing, setFacing] = useState<CameraType>("back");
//     const [screenState, setScreenState] = useState<CameraScreenState>(
//         permission?.granted ? "viewfinder" : "permissions"
//     );
//     const [capturedUri, setCapturedUri] = useState<string | null>(null);
//     const [result, setResult] = useState<AnalysisResponse | null>(null);
//     const [error, setError] = useState<string | null>(null);


//     const requestPermission = useCallback(async () => {
//         const res = await requestPermissionAsync();
//         if (res.granted) {
//             setScreenState("viewfinder");
//         } else {
//             setError(
//                 "Camera access was denied. Enable it in Android Settings → Apps → Privo → Permissions."
//             );
//             setScreenState("error");
//         }
//     }, [requestPermissionAsync]);


//     const handleFlipCamera = useCallback(() => {
//         setFacing(prev => (prev === "back" ? "front" : "back"));
//     }, []);


//     const handleCapture = useCallback(async () => {
//         if (!cameraRef.current) return;

//         try {
//             const photo = await cameraRef.current.takePictureAsync({
//                 quality: 1,
//                 // quality: 1 — full quality, no compression.
//                 // Same reason as gallery picker: ExifTool needs the original.
//                 skipProcessing: false,
//                 // skipProcessing: false — let Expo process the raw sensor data.
//                 // skipProcessing: true can produce raw YUV on some devices
//                 // that OpenCV cannot decode.
//                 exif: false,
//                 // exif: false — Expo does not parse EXIF; ExifTool handles this.
//             });

//             if (!photo?.uri) {
//                 setError("Photo capture failed. Please try again.");
//                 return;
//             }

//             setCapturedUri(photo.uri);
//             setScreenState("captured");
//         } catch (exc) {
//             setError("Could not capture photo. Please try again.");
//             setScreenState("error");
//         }
//     }, []);


//     const handleRetake = useCallback(() => {
//         setCapturedUri(null);
//         setResult(null);
//         setError(null);
//         setScreenState("viewfinder");
//     }, []);


//     const handleAnalyze = useCallback(async () => {
//         if (!capturedUri) return;

//         setScreenState("analysing");
//         setError(null);

//         // Build UploadableImage from camera capture.
//         // Camera photos are always JPEG on Android via expo-camera.
//         const uploadable: UploadableImage = {
//             uri: capturedUri,
//             name: `capture_${Date.now()}.jpg`,
//             type: "image/jpeg",
//         };

//         try {
//             const analysisResult = await analyzeImage(uploadable);
//             setResult(analysisResult);
//             setScreenState("result");
//         } catch (err) {
//             if (err instanceof PrivoApiError) {
//                 setError(err.message);
//             } else {
//                 setError("Analysis failed. Please try again.");
//             }
//             setScreenState("error");
//         }
//     }, [capturedUri]);


//     const handleReset = useCallback(() => {
//         setCapturedUri(null);
//         setResult(null);
//         setError(null);
//         setScreenState("viewfinder");
//     }, []);


//     return {
//         screenState,
//         facing,
//         capturedUri,
//         result,
//         error,
//         cameraRef,
//         hasPermission: permission?.granted ?? false,
//         requestPermission,
//         handleFlipCamera,
//         handleCapture,
//         handleRetake,
//         handleAnalyze,
//         handleReset,
//     };
// }


/**
 * src/features/camera/useCamera.ts
 *
 * Manages camera permissions, capture state, and analysis
 * for the camera screen. Produces an UploadableImage from
 * a captured photo and passes it to analyzeImage() in api.ts.
 *
 * The camera flow:
 *   1. Request camera permission
 *   2. Show live viewfinder (CameraView renders this)
 *   3. User taps capture → photo saved to temp URI
 *   4. Viewfinder freezes — show captured frame
 *   5. Send to FastAPI via analyzeImage()
 *   6. Display results
 *   7. User retakes or proceeds to protection
 */

import { useState, useCallback, useRef, type RefObject } from "react";
import { CameraView, CameraType, useCameraPermissions } from "expo-camera";
// CameraView:          expo-camera component ref type — used to call takePictureAsync()
// CameraType:          "front" | "back"
// useCameraPermissions: hook that returns [permission, requestPermission]

import { analyzeImage, PrivoApiError, UploadableImage } from "../../lib/api";
import type { AnalysisResponse } from "../../types/analysis";


export type CameraScreenState =
    | "permissions"    // waiting for / requesting camera permission
    | "viewfinder"     // live camera preview active
    | "captured"       // photo taken, frozen preview shown
    | "analysing"      // API call in progress
    | "result"         // analysis complete
    | "error";         // something went wrong


export interface UseCameraReturn {
    /** Current screen state — drives which UI CameraView renders. */
    screenState: CameraScreenState;

    /** Camera facing direction. */
    facing: CameraType;

    /** URI of the captured photo. Set after capture, null before. */
    capturedUri: string | null;

    /** Analysis result from backend. */
    result: AnalysisResponse | null;

    /** Error message for display. */
    error: string | null;

    /** Ref passed to <CameraView> so we can call takePictureAsync(). */
    cameraRef: RefObject<CameraView | null>;

    /** Whether camera permission has been granted. */
    hasPermission: boolean;

    /** Request camera permission (called on "permissions" screen). */
    requestPermission: () => Promise<void>;

    /** Flip between front and back camera. */
    handleFlipCamera: () => void;

    /** Capture a photo. */
    handleCapture: () => Promise<void>;

    /** Discard captured photo — return to viewfinder. */
    handleRetake: () => void;

    /** Send captured photo to backend for analysis. */
    handleAnalyze: () => Promise<void>;

    /** Reset everything — return to viewfinder. */
    handleReset: () => void;
}


export function useCamera(): UseCameraReturn {
    const [permission, requestPermissionAsync] = useCameraPermissions();
    const cameraRef = useRef<CameraView | null>(null);

    const [facing, setFacing] = useState<CameraType>("back");
    const [screenState, setScreenState] = useState<CameraScreenState>(
        permission?.granted ? "viewfinder" : "permissions"
    );
    const [capturedUri, setCapturedUri] = useState<string | null>(null);
    const [result, setResult] = useState<AnalysisResponse | null>(null);
    const [error, setError] = useState<string | null>(null);


    const requestPermission = useCallback(async () => {
        const res = await requestPermissionAsync();
        if (res.granted) {
            setScreenState("viewfinder");
        } else {
            setError(
                "Camera access was denied. Enable it in Android Settings → Apps → Privo → Permissions."
            );
            setScreenState("error");
        }
    }, [requestPermissionAsync]);


    const handleFlipCamera = useCallback(() => {
        setFacing(prev => (prev === "back" ? "front" : "back"));
    }, []);


    const handleCapture = useCallback(async () => {
        if (!cameraRef.current) return;

        try {
            const photo = await cameraRef.current.takePictureAsync({
                quality: 1,
                // quality: 1 — full quality, no compression.
                // Same reason as gallery picker: ExifTool needs the original.
                skipProcessing: false,
                // skipProcessing: false — let Expo process the raw sensor data.
                // skipProcessing: true can produce raw YUV on some devices
                // that OpenCV cannot decode.
                exif: false,
                // exif: false — Expo does not parse EXIF; ExifTool handles this.
            });

            if (!photo?.uri) {
                setError("Photo capture failed. Please try again.");
                setScreenState("error");
                return;
            }

            setCapturedUri(photo.uri);
            setScreenState("captured");
        } catch (exc) {
            setError("Could not capture photo. Please try again.");
            setScreenState("error");
        }
    }, []);


    const handleRetake = useCallback(() => {
        setCapturedUri(null);
        setResult(null);
        setError(null);
        setScreenState("viewfinder");
    }, []);


    const handleAnalyze = useCallback(async () => {
        if (!capturedUri) return;

        setScreenState("analysing");
        setError(null);

        // Build UploadableImage from camera capture.
        // Camera photos are always JPEG on Android via expo-camera.
        const uploadable: UploadableImage = {
            uri: capturedUri,
            name: `capture_${Date.now()}.jpg`,
            type: "image/jpeg",
        };

        try {
            const analysisResult = await analyzeImage(uploadable);
            setResult(analysisResult);
            setScreenState("result");
        } catch (err) {
            if (err instanceof PrivoApiError) {
                setError(err.message);
            } else {
                setError("Analysis failed. Please try again.");
            }
            setScreenState("error");
        }
    }, [capturedUri]);


    const handleReset = useCallback(() => {
        setCapturedUri(null);
        setResult(null);
        setError(null);
        setScreenState("viewfinder");
    }, []);


    return {
        screenState,
        facing,
        capturedUri,
        result,
        error,
        cameraRef,
        hasPermission: permission?.granted ?? false,
        requestPermission,
        handleFlipCamera,
        handleCapture,
        handleRetake,
        handleAnalyze,
        handleReset,
    };
}
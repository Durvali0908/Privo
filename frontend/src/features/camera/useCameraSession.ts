/**
 * src/features/camera/useCameraSession.ts
 *
 * Saves the captured image to Privo's permanent directory
 * using expo-file-system only.
 *
 * No database. No SQLite.
 * Gallery indexing is deferred to Week 9 when the Gallery
 * screen is built — at that point a lightweight index is
 * added here if genuinely required.
 */

import { useState, useCallback } from "react";
import * as FileSystem from "expo-file-system/legacy";
import type { AnalysisResponse } from "../../types/analysis";

const PRIVO_DIR = `${FileSystem.documentDirectory}privo_gallery/`;

export interface UseCameraSessionReturn {
    saving: boolean;
    saveError: string | null;
    savedUri: string | null;
    save: (capturedUri: string, result: AnalysisResponse) => Promise<boolean>;
}

export function useCameraSession(): UseCameraSessionReturn {
    const [saving, setSaving] = useState(false);
    const [saveError, setSaveError] = useState<string | null>(null);
    const [savedUri, setSavedUri] = useState<string | null>(null);

    const save = useCallback(async (
        capturedUri: string,
        _result: AnalysisResponse       // reserved for Week 9 provenance
    ): Promise<boolean> => {
        setSaving(true);
        setSaveError(null);

        try {
            // Ensure Privo directory exists
            const dirInfo = await FileSystem.getInfoAsync(PRIVO_DIR);
            if (!dirInfo.exists) {
                await FileSystem.makeDirectoryAsync(PRIVO_DIR, { intermediates: true });
            }

            // Copy temp capture → permanent location
            const filename = `privo_${Date.now()}.jpg`;
            const destUri = `${PRIVO_DIR}${filename}`;
            await FileSystem.copyAsync({ from: capturedUri, to: destUri });

            setSavedUri(destUri);
            return true;

        } catch (err) {
            setSaveError(
                err instanceof Error
                    ? `Could not save image: ${err.message}`
                    : "Could not save image."
            );
            return false;

        } finally {
            setSaving(false);
        }
    }, []);

    return { saving, saveError, savedUri, save };
}
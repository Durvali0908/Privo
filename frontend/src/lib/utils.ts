/**
 * src/lib/utils.ts
 *
 * PURPOSE
 * -------
 * Pure helper functions used across multiple components and hooks.
 *
 * RULES FOR THIS FILE
 * -------------------
 * - No React imports. No React Native imports.
 * - No side effects. Every function is pure (same input = same output).
 * - No API calls. No state.
 * - A function moves here only when two or more files need it.
 *
 * These functions are plain TypeScript — they would work identically
 * in a Node.js script, a web browser, or React Native.
 * That makes them easy to test without any framework setup.
 *
 * HOW THIS FILE IS USED
 * ----------------------
 * src/features/upload/UploadZone.tsx
 *   → formatBytes(result.file_size_bytes)
 *
 * src/features/session/ResultsPanel.tsx (Week 3)
 *   → formatExifDate(finding.value)
 *   → getCategoryLabel(finding.category)
 *
 * src/features/gallery/GalleryItem.tsx (Week 9)
 *   → formatBytes(item.file_size)
 *   → formatExifDate(item.created_at)
 */

import { CATEGORY_LABELS } from "./constants";
import type { FindingSeverity } from "../types/analysis";


// ─────────────────────────────────────────────────────────────────
// FILE SIZE
// ─────────────────────────────────────────────────────────────────

/**
 * Converts a raw byte count to a human-readable file size string.
 *
 * EXAMPLES
 * --------
 * formatBytes(null)      → "Unknown size"
 * formatBytes(0)         → "0 B"
 * formatBytes(512)       → "512 B"
 * formatBytes(2048)      → "2.0 KB"
 * formatBytes(2457600)   → "2.3 MB"
 * formatBytes(1073741824)→ "1.0 GB"
 *
 * PARAMETERS
 * ----------
 * bytes : number | null
 *   Raw byte count from AnalysisResponse.file_size_bytes.
 *   null is valid — backend may not know the size.
 *
 * decimals : number (default 1)
 *   Number of decimal places in the output.
 *   1 decimal is enough for UI display — "2.3 MB" not "2.34 MB".
 */
export function formatBytes(
    bytes: number | null,
    decimals: number = 1
): string {
    if (bytes === null || bytes === undefined) return "Unknown size";
    if (bytes === 0) return "0 B";

    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    // Math.floor(Math.log(bytes) / Math.log(1024)):
    //   bytes=512     → log(512)/log(1024) = 0.9 → floor = 0 → "B"
    //   bytes=2048    → log(2048)/log(1024) = 1.1 → floor = 1 → "KB"
    //   bytes=2457600 → log(2457600)/log(1024) = 2.38 → floor = 2 → "MB"

    const value = (bytes / Math.pow(k, i)).toFixed(decimals);
    return `${value} ${sizes[i]}`;
}


// ─────────────────────────────────────────────────────────────────
// DATE / TIMESTAMP
// ─────────────────────────────────────────────────────────────────

/**
 * Formats an ExifTool timestamp string into a readable date.
 *
 * ExifTool returns timestamps in the format: "YYYY:MM:DD HH:MM:SS"
 * This is not ISO 8601 format — the date separators are colons,
 * not dashes. JavaScript's Date constructor cannot parse it directly.
 *
 * EXAMPLES
 * --------
 * formatExifDate("2024:08:15 14:23:01") → "15 Aug 2024, 14:23"
 * formatExifDate("2024:01:01 00:00:00") → "1 Jan 2024, 00:00"
 * formatExifDate(null)                   → "Unknown date"
 * formatExifDate("invalid")              → "Invalid date"
 *
 * PARAMETERS
 * ----------
 * exifDate : string | null
 *   Raw timestamp from RawMetadata fields:
 *   datetime_original, create_date, modify_date, etc.
 */
export function formatExifDate(exifDate: string | null): string {
    if (!exifDate) return "Unknown date";

    try {
        // Convert "YYYY:MM:DD HH:MM:SS" → "YYYY-MM-DDTHH:MM:SS"
        // Replace first two colons in the date part with dashes.
        const isoString = exifDate
            .replace(/^(\d{4}):(\d{2}):(\d{2})/, "$1-$2-$3")
            .replace(" ", "T");
        // "2024:08:15 14:23:01"
        //   → "2024-08-15 14:23:01"  (first replace)
        //   → "2024-08-15T14:23:01"  (second replace)

        const date = new Date(isoString);

        if (isNaN(date.getTime())) {
            // getTime() returns NaN for invalid dates.
            return "Invalid date";
        }

        return date.toLocaleString("en-IN", {
            // en-IN: Indian English locale — appropriate for Privo's target market.
            day: "numeric",
            month: "short",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
        });
        // Example output: "15 Aug 2024, 14:23"

    } catch {
        return "Invalid date";
    }
}

/**
 * Formats a GPS timestamp from ExifTool.
 *
 * GPS timestamps come as separate date and time fields:
 *   gps_date_stamp: "2024:08:15"
 *   gps_time_stamp: "06:23:01"  (UTC)
 *
 * EXAMPLES
 * --------
 * formatGpsTimestamp("2024:08:15", "06:23:01") → "15 Aug 2024, 06:23 UTC"
 * formatGpsTimestamp(null, null)                → "Unknown GPS time"
 * formatGpsTimestamp("2024:08:15", null)        → "15 Aug 2024"
 */
export function formatGpsTimestamp(
    dateStamp: string | null,
    timeStamp: string | null
): string {
    if (!dateStamp && !timeStamp) return "Unknown GPS time";

    try {
        if (dateStamp) {
            const datePart = dateStamp.replace(/:/g, "-");
            // "2024:08:15" → "2024-08-15"

            const date = new Date(datePart);
            if (isNaN(date.getTime())) return "Invalid GPS date";

            const dateLabel = date.toLocaleString("en-IN", {
                day: "numeric",
                month: "short",
                year: "numeric",
            });

            if (timeStamp) {
                // Remove sub-second precision if present: "06:23:01.000" → "06:23"
                const timePart = timeStamp.slice(0, 5);
                return `${dateLabel}, ${timePart} UTC`;
            }

            return dateLabel;
        }

        return timeStamp ? `${timeStamp} UTC` : "Unknown GPS time";

    } catch {
        return "Invalid GPS time";
    }
}


// ─────────────────────────────────────────────────────────────────
// CATEGORY AND SEVERITY LABELS
// ─────────────────────────────────────────────────────────────────

/**
 * Returns the human-readable label for an exposure category.
 *
 * EXAMPLES
 * --------
 * getCategoryLabel("location_exposure") → "Location Exposure"
 * getCategoryLabel("travel_exposure")   → "Travel Pattern"
 * getCategoryLabel("unknown_category")  → "unknown_category"
 *
 * Falls back to the raw string if the category is not in
 * CATEGORY_LABELS — future-safe for new categories added
 * to the backend before this file is updated.
 */
export function getCategoryLabel(category: string): string {
    return CATEGORY_LABELS[category] ?? category;
    // ?? category: if the key is not in CATEGORY_LABELS,
    // return the raw string rather than crashing.
}

/**
 * Returns the human-readable label for a severity level.
 *
 * EXAMPLES
 * --------
 * getSeverityLabel("high")   → "High Risk"
 * getSeverityLabel("medium") → "Medium Risk"
 * getSeverityLabel("low")    → "Low Risk"
 */
export function getSeverityLabel(severity: FindingSeverity): string {
    const labels: Record<FindingSeverity, string> = {
        high: "High Risk",
        medium: "Medium Risk",
        low: "Low Risk",
    };
    return labels[severity];
}


// ─────────────────────────────────────────────────────────────────
// STRING HELPERS
// ─────────────────────────────────────────────────────────────────

/**
 * Capitalises the first letter of a string.
 *
 * EXAMPLES
 * --------
 * capitalise("gallery") → "Gallery"
 * capitalise("camera")  → "Camera"
 * capitalise("")        → ""
 */
export function capitalise(str: string): string {
    if (!str) return str;
    return str.charAt(0).toUpperCase() + str.slice(1);
}

/**
 * Truncates a string to a maximum length, adding "…" if truncated.
 *
 * Used to shorten long metadata values (file paths, descriptions)
 * that would overflow a single-line UI element.
 *
 * EXAMPLES
 * --------
 * truncate("Hello World", 8)  → "Hello Wo…"
 * truncate("Hi", 8)           → "Hi"
 * truncate("", 8)             → ""
 */
export function truncate(str: string, maxLength: number): string {
    if (!str) return str;
    if (str.length <= maxLength) return str;
    return str.slice(0, maxLength) + "…";
}


// ─────────────────────────────────────────────────────────────────
// FINDINGS HELPERS
// ─────────────────────────────────────────────────────────────────

/**
 * Returns the count of findings at each severity level.
 *
 * Used by the risk summary header to show:
 *   "2 high  •  1 medium  •  3 low"
 *
 * EXAMPLE
 * -------
 * countBySeverity([
 *   { severity: "high", ... },
 *   { severity: "high", ... },
 *   { severity: "low",  ... },
 * ])
 * → { high: 2, medium: 0, low: 1 }
 */
export function countBySeverity(
    findings: Array<{ severity: FindingSeverity }>
): Record<FindingSeverity, number> {
    return findings.reduce(
        (acc, finding) => {
            acc[finding.severity] += 1;
            return acc;
        },
        { high: 0, medium: 0, low: 0 } as Record<FindingSeverity, number>
    );
}

/**
 * Sorts findings by severity — high first, then medium, then low.
 * Returns a new array — does not mutate the original.
 *
 * Used by the findings list to always show the most important
 * findings at the top without requiring manual ordering.
 */
export function sortFindingsBySeverity<T extends { severity: FindingSeverity }>(
    findings: T[]
): T[] {
    const order: Record<FindingSeverity, number> = {
        high: 0,
        medium: 1,
        low: 2,
    };
    return [...findings].sort(
        (a, b) => order[a.severity] - order[b.severity]
    );
}
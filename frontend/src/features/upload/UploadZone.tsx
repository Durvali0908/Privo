/**
 * src/features/upload/UploadZone.tsx
 *
 * PURPOSE
 * -------
 * The upload screen component. Renders the complete upload UI
 * across all possible states. Contains zero business logic —
 * all state and behaviour comes from useUpload().
 *
 * ─────────────────────────────────────────────────────────────────
 * WHAT THIS COMPONENT RENDERS
 * ─────────────────────────────────────────────────────────────────
 * State 1 — No image:     picker prompt + Select button
 * State 2 — Image ready:  preview + filename + Analyse button
 * State 3 — Loading:      spinner + disabled button
 * State 4 — Result:       session info + metadata findings list
 * State 5 — Error:        red error box + message
 *
 * ─────────────────────────────────────────────────────────────────
 * REACT NATIVE VS WEB DIFFERENCES
 * ─────────────────────────────────────────────────────────────────
 * Web                      React Native
 * ──────────────────────   ──────────────────────────────────────
 * <div>                 →  <View>
 * <p>, <span>           →  <Text>
 * <img>                 →  <Image>
 * <button>              →  <TouchableOpacity> + <Text>
 * <input type="file">   →  expo-image-picker (no DOM input)
 * className="..."       →  style={styles.xxx}
 * Tailwind CSS          →  StyleSheet.create({})
 * scroll: overflow-y    →  <ScrollView>
 * onClick               →  onPress
 *
 * ─────────────────────────────────────────────────────────────────
 * HOW THIS FILE COMMUNICATES WITH OTHER MODULES
 * ─────────────────────────────────────────────────────────────────
 * Calls:
 *   src/features/upload/useUpload.ts
 *     → all state and handlers via useUpload()
 *
 * Imports from:
 *   src/lib/constants.ts → SEVERITY_COLOURS, APP_NAME, APP_TAGLINE
 *   src/lib/utils.ts     → getCategoryLabel, getSeverityLabel,
 *                           sortFindingsBySeverity, countBySeverity
 *   src/types/analysis.ts → MetadataFinding, MetadataSummary
 *
 * Used by:
 *   App.tsx → renders <UploadZone /> as the main screen
 *   Future: app/index.tsx when Expo Router navigation is added
 */

import React from "react";
import {
    View,
    Text,
    Image,
    TouchableOpacity,
    ScrollView,
    ActivityIndicator,
    StyleSheet,
    SafeAreaView,
    Platform,
} from "react-native";
// View:              Container — equivalent to <div>
// Text:              All visible text — no bare strings in RN JSX
// Image:             Renders images from URIs or bundled assets
// TouchableOpacity:  Pressable container — fades on press
// ScrollView:        Scrollable container — needed when content
//                    may exceed screen height
// ActivityIndicator: Native loading spinner — uses OS-native animation
// StyleSheet:        Creates optimised style objects (like CSS-in-JS)
// SafeAreaView:      Respects notch/status bar on modern phones
// Platform:          Detects OS — used for platform-specific values

import { useUpload } from "./useUpload";
import {
    SEVERITY_COLOURS,
    APP_NAME,
    APP_TAGLINE,
} from "../../lib/constants";
import {
    getCategoryLabel,
    getSeverityLabel,
    sortFindingsBySeverity,
    countBySeverity,
} from "../../lib/utils";
import type {
    MetadataFinding,
    MetadataSummary,
    DetectionSummary,
} from "../../types/analysis";



// ─────────────────────────────────────────────────────────────────
// DETECTION SECTION (Week 3)
// ─────────────────────────────────────────────────────────────────

function DetectionSection({ detection }: { detection: DetectionSummary }) {
    if (!detection.success) {
        return (
            <View style={styles.metadataSection}>
                <Text style={styles.sectionTitle}>Detection</Text>
                <View style={styles.warningBox}>
                    <Text style={styles.warningText}>
                        Detection could not run.{detection.error ? ` ${detection.error}` : ""}
                    </Text>
                </View>
            </View>
        );
    }

    const hasDetections = detection.total_regions > 0;

    return (
        <View style={styles.metadataSection}>
            <View style={styles.sectionHeaderRow}>
                <Text style={styles.sectionTitle}>Detection</Text>
                <Text style={styles.findingCount}>
                    {detection.total_regions} region{detection.total_regions !== 1 ? "s" : ""}
                </Text>
            </View>

            {/* Summary row */}
            <View style={styles.detectionSummaryRow}>
                <DetectionPill label="Faces" count={detection.face_count} colour="#FF6B6B" />
                <DetectionPill label="QR Codes" count={detection.qr_count} colour="#FFB347" />
                <DetectionPill label="Text" count={detection.text_count} colour="#94A3B8" />
            </View>

            {!hasDetections && (
                <View style={styles.cleanBox}>
                    <Text style={styles.cleanText}>
                        ✓ No faces, QR codes, or text regions detected.
                    </Text>
                </View>
            )}

            {/* QR content */}
            {detection.regions
                .filter(r => r.region_type === "qr_code" && r.content)
                .map((r, i) => (
                    <View key={`qr-${i}`} style={styles.findingRow}>
                        <Text style={styles.findingFieldName}>QR Code Content</Text>
                        <Text style={styles.findingValue} numberOfLines={3}>{r.content}</Text>
                        <Text style={styles.findingExplanation}>
                            This QR code may contain a URL, contact, or identifier.
                        </Text>
                    </View>
                ))
            }

            {/* Text samples — first 3 only to avoid overwhelming the UI */}
            {detection.regions
                .filter(r => r.region_type === "text" && r.content)
                .slice(0, 3)
                .map((r, i) => (
                    <View key={`text-${i}`} style={styles.findingRow}>
                        <Text style={styles.findingFieldName}>
                            Text Region (confidence: {Math.round(r.confidence * 100)}%)
                        </Text>
                        <Text style={styles.findingValue} numberOfLines={2}>{r.content}</Text>
                    </View>
                ))
            }
            {detection.text_count > 3 && (
                <Text style={styles.sessionMessage}>
                    +{detection.text_count - 3} more text region{detection.text_count - 3 !== 1 ? "s" : ""} detected.
                </Text>
            )}
        </View>
    );
}

function DetectionPill({
    label,
    count,
    colour,
}: {
    label: string;
    count: number;
    colour: string;
}) {
    return (
        <View style={styles.detectionPill}>
            <Text style={[styles.detectionPillCount, { color: count > 0 ? colour : "#475569" }]}>
                {count}
            </Text>
            <Text style={styles.detectionPillLabel}>{label}</Text>
        </View>
    );
}

// ─────────────────────────────────────────────────────────────────
// SUB-COMPONENTS
// Small focused components extracted to keep the main component
// readable. Each renders one specific section of the UI.
// ─────────────────────────────────────────────────────────────────

/**
 * Severity badge shown on each finding row.
 * Colour comes from SEVERITY_COLOURS in constants.ts.
 */
function SeverityBadge({ severity }: { severity: string }) {
    const colours = SEVERITY_COLOURS[severity as keyof typeof SEVERITY_COLOURS]
        ?? SEVERITY_COLOURS.low;

    return (
        <View style={[
            styles.badge,
            {
                backgroundColor: colours.background,
                borderColor: colours.border,
            }
        ]}>
            <Text style={[styles.badgeText, { color: colours.text }]}>
                {getSeverityLabel(severity as "high" | "medium" | "low")}
            </Text>
        </View>
    );
}


/**
 * Renders one privacy finding row.
 * Shows severity badge, category label, field name, value,
 * and the plain-English explanation.
 */
function FindingRow({ finding }: { finding: MetadataFinding }) {
    return (
        <View style={styles.findingRow}>
            {/* Top row: badge + category */}
            <View style={styles.findingHeader}>
                <SeverityBadge severity={finding.severity} />
                <Text style={styles.findingCategory}>
                    {getCategoryLabel(finding.category)}
                </Text>
                {finding.is_combination && (
                    <View style={styles.combinationTag}>
                        <Text style={styles.combinationTagText}>Combined</Text>
                    </View>
                    // "Combined" tag shown when a finding is raised by two or
                    // more fields together (e.g. GPS + timestamp → travel exposure).
                )}
            </View>

            {/* Field name */}
            <Text style={styles.findingFieldName}>{finding.field_name}</Text>

            {/* Actual value found */}
            <Text style={styles.findingValue} numberOfLines={2}>
                {finding.value}
            </Text>
            {/* numberOfLines={2}: truncates very long values (e.g. long GPS strings)
          to prevent overflow on narrow screens. */}

            {/* Plain-English explanation */}
            <Text style={styles.findingExplanation}>
                {finding.explanation}
            </Text>
        </View>
    );
}


/**
 * Renders the full metadata results section.
 * Handles three cases:
 *   extraction failed → warning message
 *   extraction success, no findings → clean metadata message
 *   extraction success, findings → sorted findings list
 */
function MetadataSection({ metadata }: { metadata: MetadataSummary }) {
    // Extraction failed — ExifTool could not run
    if (!metadata.extraction_success) {
        return (
            <View style={styles.metadataSection}>
                <Text style={styles.sectionTitle}>Metadata Analysis</Text>
                <View style={styles.warningBox}>
                    <Text style={styles.warningText}>
                        Metadata could not be read. The image may have been processed
                        by an app that stripped its metadata — or ExifTool may not
                        be running on the server.
                    </Text>
                </View>
            </View>
        );
    }

    // Extraction success but no findings — clean metadata
    if (metadata.total_findings === 0) {
        return (
            <View style={styles.metadataSection}>
                <Text style={styles.sectionTitle}>Metadata Analysis</Text>
                <View style={styles.cleanBox}>
                    <Text style={styles.cleanText}>
                        ✓ No metadata concerns found. This image appears to have
                        clean or stripped metadata.
                    </Text>
                </View>
            </View>
        );
    }

    // Sort findings: high → medium → low
    const sorted = sortFindingsBySeverity(metadata.findings);
    const counts = countBySeverity(metadata.findings);

    return (
        <View style={styles.metadataSection}>
            {/* Section header with finding count */}
            <View style={styles.sectionHeaderRow}>
                <Text style={styles.sectionTitle}>Metadata Findings</Text>
                <Text style={styles.findingCount}>
                    {metadata.total_findings} concern{metadata.total_findings !== 1 ? "s" : ""}
                </Text>
            </View>

            {/* Severity summary row */}
            <View style={styles.severitySummary}>
                {counts.high > 0 && (
                    <Text style={[styles.severityCount, { color: SEVERITY_COLOURS.high.text }]}>
                        {counts.high} high
                    </Text>
                )}
                {counts.medium > 0 && (
                    <Text style={[styles.severityCount, { color: SEVERITY_COLOURS.medium.text }]}>
                        {counts.medium} medium
                    </Text>
                )}
                {counts.low > 0 && (
                    <Text style={[styles.severityCount, { color: SEVERITY_COLOURS.low.text }]}>
                        {counts.low} low
                    </Text>
                )}
            </View>

            {/* Findings list */}
            {sorted.map((finding, index) => (
                <FindingRow
                    key={`${finding.field_name}-${index}`}
                    finding={finding}
                />
                // key: React needs a unique key per list item for efficient
                // re-rendering. field_name + index is unique for this list
                // because each field appears at most once per image.
            ))}
        </View>
    );
}


/**
 * Session details section — shown after successful analysis.
 * Displays session ID, source, status, and settings confirmation.
 */
function SessionDetails({
    sessionId,
    source,
    status,
    settingsLoaded,
    message,
}: {
    sessionId: string;
    source: string;
    status: string;
    settingsLoaded: boolean;
    message: string;
}) {
    return (
        <View style={styles.sessionSection}>
            <View style={styles.sessionRow}>
                <Text style={styles.sessionLabel}>Session</Text>
                <Text style={styles.sessionValue} numberOfLines={1}>
                    {sessionId}
                </Text>
            </View>
            <View style={styles.sessionRow}>
                <Text style={styles.sessionLabel}>Source</Text>
                <Text style={styles.sessionValue}>{source}</Text>
            </View>
            <View style={styles.sessionRow}>
                <Text style={styles.sessionLabel}>Status</Text>
                <Text style={styles.sessionValue}>{status}</Text>
            </View>
            <View style={styles.sessionRow}>
                <Text style={styles.sessionLabel}>Settings</Text>
                <Text style={styles.sessionValue}>
                    {settingsLoaded ? "Loaded ✓" : "Not loaded"}
                </Text>
            </View>
            <Text style={styles.sessionMessage}>{message}</Text>
        </View>
    );
}


// ─────────────────────────────────────────────────────────────────
// MAIN COMPONENT
// ─────────────────────────────────────────────────────────────────

/**
 * UploadZone — the complete upload screen.
 *
 * Takes no props. All state comes from useUpload().
 * Renders different content based on the current upload state.
 */
export function UploadZone() {
    const {
        asset,
        previewUri,
        fileSizeLabel,
        loading,
        result,
        error,
        handlePickImage,
        handleAnalyze,
        handleReset,
    } = useUpload();

    return (
        <SafeAreaView style={styles.safeArea}>
            {/* SafeAreaView: pads content away from notch and status bar.
          Essential on modern Android phones with punch-hole cameras. */}

            <ScrollView
                style={styles.scrollView}
                contentContainerStyle={styles.scrollContent}
                showsVerticalScrollIndicator={false}
            // showsVerticalScrollIndicator: false — hides the scroll bar
            // for a cleaner look. Content is still scrollable.
            >

                {/* ── APP HEADER ────────────────────────────────────── */}
                <View style={styles.header}>
                    <Text style={styles.appName}>{APP_NAME}</Text>
                    <Text style={styles.appTagline}>{APP_TAGLINE}</Text>
                </View>

                {/* ── STATE 1: NO IMAGE SELECTED ────────────────────── */}
                {!asset && (
                    <View style={styles.emptyState}>
                        {/* Shield icon placeholder */}
                        <View style={styles.shieldIcon}>
                            <Text style={styles.shieldEmoji}>🛡️</Text>
                        </View>

                        <Text style={styles.emptyTitle}>
                            Select an image to analyse
                        </Text>
                        <Text style={styles.emptySubtitle}>
                            JPG, PNG, WebP, HEIC · up to 20 MB
                        </Text>

                        <TouchableOpacity
                            style={styles.primaryButton}
                            onPress={handlePickImage}
                            activeOpacity={0.8}
                        // activeOpacity: how transparent the button becomes
                        // when pressed. 0.8 = 80% opacity → subtle press effect.
                        >
                            <Text style={styles.primaryButtonText}>Select Image</Text>
                        </TouchableOpacity>
                    </View>
                )}

                {/* ── STATE 2 & 3: IMAGE SELECTED ───────────────────── */}
                {asset && (
                    <View style={styles.card}>

                        {/* Image preview */}
                        {previewUri && (
                            <Image
                                source={{ uri: previewUri }}
                                style={styles.previewImage}
                                resizeMode="contain"
                            // resizeMode="contain": shows full image without cropping,
                            // letterboxing if needed. Preserves aspect ratio.
                            />
                        )}

                        {/* File info row */}
                        <View style={styles.fileInfo}>
                            <View style={styles.fileInfoLeft}>
                                <Text style={styles.fileName} numberOfLines={1}>
                                    {asset.fileName ?? "Selected image"}
                                </Text>
                                {fileSizeLabel && (
                                    <Text style={styles.fileSize}>{fileSizeLabel}</Text>
                                )}
                            </View>

                            {/* Remove button — hidden during loading */}
                            {!loading && (
                                <TouchableOpacity
                                    onPress={handleReset}
                                    hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
                                // hitSlop: extends the touchable area beyond the
                                // visual bounds. Makes small buttons easier to tap
                                // on a phone without a precise mouse cursor.
                                >
                                    <Text style={styles.removeButton}>Remove</Text>
                                </TouchableOpacity>
                            )}
                        </View>

                        {/* Analyse button */}
                        <TouchableOpacity
                            style={[
                                styles.primaryButton,
                                loading && styles.primaryButtonDisabled,
                            ]}
                            onPress={handleAnalyze}
                            disabled={loading}
                            activeOpacity={0.8}
                        >
                            {loading ? (
                                <View style={styles.loadingRow}>
                                    <ActivityIndicator
                                        size="small"
                                        color="#FFFFFF"
                                    // ActivityIndicator: React Native's built-in spinner.
                                    // Uses the native Android spinner animation.
                                    // No external library needed.
                                    />
                                    <Text style={styles.primaryButtonText}>  Analysing...</Text>
                                </View>
                            ) : (
                                <Text style={styles.primaryButtonText}>Analyse Image</Text>
                            )}
                        </TouchableOpacity>

                    </View>
                )}

                {/* ── STATE 4: ERROR ─────────────────────────────────── */}
                {error && (
                    <View style={styles.errorBox}>
                        <Text style={styles.errorIcon}>⚠️</Text>
                        <Text style={styles.errorText}>{error}</Text>
                    </View>
                )}

                {/* ── STATE 5: RESULT ────────────────────────────────── */}
                {result && (
                    <View style={styles.resultContainer}>

                        {/* Pipeline ready indicator */}
                        <View style={styles.pipelineHeader}>
                            <View style={styles.pipelineDot} />
                            <Text style={styles.pipelineLabel}>Pipeline Ready</Text>
                            <Text style={styles.pipelineStatus}>
                                {result.status.toUpperCase()}
                            </Text>
                        </View>

                        {/* Session details */}
                        <SessionDetails
                            sessionId={result.session_id}
                            source={result.source}
                            status={result.status}
                            settingsLoaded={result.settings_loaded}
                            message={result.message}
                        />

                        {/* Metadata findings */}
                        {result.metadata && (
                            <MetadataSection metadata={result.metadata} />
                        )}

                        {/* Detection results */}
                        {result.detection && (
                            <DetectionSection detection={result.detection} />
                        )}

                        {/* Analyse another button */}
                        <TouchableOpacity
                            style={styles.secondaryButton}
                            onPress={handleReset}
                            activeOpacity={0.7}
                        >
                            <Text style={styles.secondaryButtonText}>
                                Analyse Another Image
                            </Text>
                        </TouchableOpacity>

                    </View>
                )}

            </ScrollView>
        </SafeAreaView>
    );
}


// ─────────────────────────────────────────────────────────────────
// STYLES
// ─────────────────────────────────────────────────────────────────

const COLOURS = {
    background: "#020617",   // slate-950 — main background
    surface: "#0F172A",   // slate-900 — card background
    surfaceAlt: "#1E293B",   // slate-800 — subtle surface
    border: "#334155",   // slate-700 — dividers
    textPrimary: "#F1F5F9",   // slate-100 — main text
    textSecond: "#94A3B8",   // slate-400 — secondary text
    textMuted: "#475569",   // slate-600 — muted text
    accent: "#7C3AED",   // violet-700 — primary accent
    accentLight: "#8B5CF6",   // violet-500 — hover accent
    success: "#10B981",   // emerald-500 — success green
    errorBg: "#1C0A0A",   // deep red background
    errorBorder: "#7F1D1D",   // red-900 — error border
    errorText: "#FCA5A5",   // red-300 — error text
    warningBg: "#1C1000",   // deep amber background
    warningText: "#FCD34D",   // amber-300 — warning text
};

const styles = StyleSheet.create({
    // ── LAYOUT ──────────────────────────────────────────────────
    safeArea: {
        flex: 1,
        backgroundColor: COLOURS.background,
    },
    scrollView: {
        flex: 1,
    },
    scrollContent: {
        paddingHorizontal: 16,
        paddingBottom: 40,
        paddingTop: Platform.OS === "android" ? 16 : 0,
        // Extra top padding on Android — SafeAreaView does not account
        // for the status bar on all Android versions.
    },

    // ── HEADER ──────────────────────────────────────────────────
    header: {
        alignItems: "center",
        paddingVertical: 28,
    },
    appName: {
        fontSize: 26,
        fontWeight: "700",
        color: COLOURS.textPrimary,
        letterSpacing: 0.5,
    },
    appTagline: {
        fontSize: 13,
        color: COLOURS.textSecond,
        marginTop: 4,
    },

    // ── EMPTY STATE ─────────────────────────────────────────────
    emptyState: {
        alignItems: "center",
        paddingVertical: 48,
        gap: 16,
        // gap: spacing between child elements — React Native 0.71+
    },
    shieldIcon: {
        width: 72,
        height: 72,
        borderRadius: 20,
        backgroundColor: "rgba(124,58,237,0.15)",
        alignItems: "center",
        justifyContent: "center",
    },
    shieldEmoji: {
        fontSize: 32,
    },
    emptyTitle: {
        fontSize: 16,
        fontWeight: "600",
        color: COLOURS.textPrimary,
        textAlign: "center",
    },
    emptySubtitle: {
        fontSize: 13,
        color: COLOURS.textMuted,
        textAlign: "center",
    },

    // ── CARD (image selected) ────────────────────────────────────
    card: {
        backgroundColor: COLOURS.surface,
        borderRadius: 16,
        borderWidth: 1,
        borderColor: COLOURS.border,
        overflow: "hidden",
        // overflow: "hidden" clips the image preview to the card's
        // rounded corners.
    },
    previewImage: {
        width: "100%",
        height: 220,
        backgroundColor: COLOURS.background,
    },
    fileInfo: {
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
        paddingHorizontal: 16,
        paddingVertical: 12,
    },
    fileInfoLeft: {
        flex: 1,
        marginRight: 12,
    },
    fileName: {
        fontSize: 14,
        fontWeight: "500",
        color: COLOURS.textPrimary,
    },
    fileSize: {
        fontSize: 12,
        color: COLOURS.textSecond,
        marginTop: 2,
    },
    removeButton: {
        fontSize: 13,
        color: COLOURS.textMuted,
    },

    // ── BUTTONS ──────────────────────────────────────────────────
    primaryButton: {
        backgroundColor: COLOURS.accent,
        borderRadius: 10,
        paddingVertical: 14,
        alignItems: "center",
        marginHorizontal: 16,
        marginBottom: 16,
        marginTop: 4,
    },
    primaryButtonDisabled: {
        opacity: 0.6,
    },
    primaryButtonText: {
        color: "#FFFFFF",
        fontSize: 15,
        fontWeight: "600",
    },
    loadingRow: {
        flexDirection: "row",
        alignItems: "center",
    },
    secondaryButton: {
        paddingVertical: 14,
        alignItems: "center",
        marginTop: 8,
    },
    secondaryButtonText: {
        color: COLOURS.textSecond,
        fontSize: 14,
    },

    // ── ERROR BOX ────────────────────────────────────────────────
    errorBox: {
        flexDirection: "row",
        alignItems: "flex-start",
        backgroundColor: COLOURS.errorBg,
        borderWidth: 1,
        borderColor: COLOURS.errorBorder,
        borderRadius: 12,
        padding: 14,
        marginTop: 12,
        gap: 10,
    },
    errorIcon: {
        fontSize: 16,
        marginTop: 1,
    },
    errorText: {
        flex: 1,
        fontSize: 13,
        color: COLOURS.errorText,
        lineHeight: 20,
    },

    // ── RESULT CONTAINER ─────────────────────────────────────────
    resultContainer: {
        marginTop: 16,
        gap: 12,
    },

    // ── PIPELINE HEADER ──────────────────────────────────────────
    pipelineHeader: {
        flexDirection: "row",
        alignItems: "center",
        backgroundColor: "rgba(124,58,237,0.1)",
        borderWidth: 1,
        borderColor: "rgba(124,58,237,0.3)",
        borderRadius: 12,
        paddingHorizontal: 14,
        paddingVertical: 10,
        gap: 8,
    },
    pipelineDot: {
        width: 8,
        height: 8,
        borderRadius: 4,
        backgroundColor: COLOURS.success,
    },
    pipelineLabel: {
        flex: 1,
        fontSize: 14,
        fontWeight: "500",
        color: COLOURS.textPrimary,
    },
    pipelineStatus: {
        fontSize: 11,
        fontWeight: "600",
        color: COLOURS.accentLight,
        letterSpacing: 0.5,
    },

    // ── SESSION DETAILS ──────────────────────────────────────────
    sessionSection: {
        backgroundColor: COLOURS.surface,
        borderRadius: 12,
        borderWidth: 1,
        borderColor: COLOURS.border,
        paddingHorizontal: 14,
        paddingTop: 12,
        paddingBottom: 4,
    },
    sessionRow: {
        flexDirection: "row",
        justifyContent: "space-between",
        alignItems: "center",
        paddingVertical: 8,
        borderBottomWidth: 1,
        borderBottomColor: COLOURS.surfaceAlt,
    },
    sessionLabel: {
        fontSize: 13,
        color: COLOURS.textSecond,
    },
    sessionValue: {
        fontSize: 13,
        fontFamily: Platform.OS === "android" ? "monospace" : "Courier",
        color: COLOURS.textPrimary,
        maxWidth: "65%",
        // maxWidth prevents very long session IDs from pushing
        // the label off screen on narrow phones.
    },
    sessionMessage: {
        fontSize: 12,
        color: COLOURS.textMuted,
        paddingVertical: 10,
        lineHeight: 18,
    },

    // ── METADATA SECTION ─────────────────────────────────────────
    metadataSection: {
        gap: 10,
    },
    sectionHeaderRow: {
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
    },
    sectionTitle: {
        fontSize: 15,
        fontWeight: "600",
        color: COLOURS.textPrimary,
    },
    findingCount: {
        fontSize: 13,
        color: COLOURS.textSecond,
    },
    severitySummary: {
        flexDirection: "row",
        gap: 12,
    },
    severityCount: {
        fontSize: 13,
        fontWeight: "500",
    },
    warningBox: {
        backgroundColor: COLOURS.warningBg,
        borderRadius: 10,
        padding: 14,
    },
    warningText: {
        fontSize: 13,
        color: COLOURS.warningText,
        lineHeight: 20,
    },
    cleanBox: {
        backgroundColor: "rgba(16,185,129,0.1)",
        borderRadius: 10,
        padding: 14,
        borderWidth: 1,
        borderColor: "rgba(16,185,129,0.2)",
    },
    cleanText: {
        fontSize: 13,
        color: COLOURS.success,
        lineHeight: 20,
    },

    // ── FINDING ROW ──────────────────────────────────────────────
    findingRow: {
        backgroundColor: COLOURS.surface,
        borderRadius: 12,
        borderWidth: 1,
        borderColor: COLOURS.border,
        padding: 14,
        gap: 6,
    },
    findingHeader: {
        flexDirection: "row",
        alignItems: "center",
        gap: 8,
        flexWrap: "wrap",
    },
    findingCategory: {
        fontSize: 13,
        fontWeight: "600",
        color: COLOURS.textPrimary,
        flex: 1,
    },
    combinationTag: {
        backgroundColor: COLOURS.surfaceAlt,
        borderRadius: 4,
        paddingHorizontal: 6,
        paddingVertical: 2,
    },
    combinationTagText: {
        fontSize: 10,
        color: COLOURS.textSecond,
        fontWeight: "500",
    },
    findingFieldName: {
        fontSize: 12,
        fontFamily: Platform.OS === "android" ? "monospace" : "Courier",
        color: COLOURS.textMuted,
    },
    findingValue: {
        fontSize: 13,
        color: COLOURS.textPrimary,
        fontWeight: "500",
    },
    findingExplanation: {
        fontSize: 12,
        color: COLOURS.textSecond,
        lineHeight: 18,
    },

    // ── DETECTION ───────────────────────────────────────────────
    detectionSummaryRow: {
        flexDirection: "row",
        gap: 12,
        marginBottom: 4,
    },
    detectionPill: {
        alignItems: "center",
        backgroundColor: "#0F172A",
        borderRadius: 10,
        borderWidth: 1,
        borderColor: "#334155",
        paddingVertical: 8,
        paddingHorizontal: 16,
        minWidth: 72,
    },
    detectionPillCount: {
        fontSize: 20,
        fontWeight: "700",
    },
    detectionPillLabel: {
        fontSize: 11,
        color: "#94A3B8",
        marginTop: 2,
    },

    // ── BADGE ────────────────────────────────────────────────────
    badge: {
        borderRadius: 6,
        borderWidth: 1,
        paddingHorizontal: 8,
        paddingVertical: 3,
    },
    badgeText: {
        fontSize: 11,
        fontWeight: "600",
    },
});

/**
 * src/features/camera/CameraView.tsx
 *
 * Camera screen. Renders different UI based on screenState from useCamera().
 * Contains zero business logic — all state and behaviour from useCamera().
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
    Dimensions,
} from "react-native";
import { CameraView as ExpoCameraView } from "expo-camera";

import { useCamera } from "./useCamera";
import { SEVERITY_COLOURS, CATEGORY_LABELS, APP_NAME } from "../../lib/constants";
import {
    getCategoryLabel,
    getSeverityLabel,
    sortFindingsBySeverity,
    countBySeverity,
} from "../../lib/utils";

const { width: SCREEN_WIDTH } = Dimensions.get("window");
const VIEWFINDER_HEIGHT = SCREEN_WIDTH * 1.2;


// ─────────────────────────────────────────────────────────────────
// SUB-COMPONENTS
// ─────────────────────────────────────────────────────────────────

function PermissionScreen({ onRequest }: { onRequest: () => void }) {
    return (
        <View style={styles.centeredScreen}>
            <Text style={styles.shieldEmoji}>🛡️</Text>
            <Text style={styles.permissionTitle}>Camera Access Required</Text>
            <Text style={styles.permissionBody}>
                Privo needs camera access to analyse images for privacy risks.
                Your images are processed locally on your laptop — nothing is
                stored or shared.
            </Text>
            <TouchableOpacity style={styles.primaryButton} onPress={onRequest} activeOpacity={0.8}>
                <Text style={styles.primaryButtonText}>Grant Camera Access</Text>
            </TouchableOpacity>
        </View>
    );
}

function ErrorScreen({ message, onRetry }: { message: string; onRetry: () => void }) {
    return (
        <View style={styles.centeredScreen}>
            <Text style={styles.errorEmoji}>⚠️</Text>
            <Text style={styles.errorText}>{message}</Text>
            <TouchableOpacity style={styles.primaryButton} onPress={onRetry} activeOpacity={0.8}>
                <Text style={styles.primaryButtonText}>Try Again</Text>
            </TouchableOpacity>
        </View>
    );
}

function SeverityBadge({ severity }: { severity: string }) {
    const colours = SEVERITY_COLOURS[severity as keyof typeof SEVERITY_COLOURS]
        ?? SEVERITY_COLOURS.low;
    return (
        <View style={[styles.badge, { backgroundColor: colours.background, borderColor: colours.border }]}>
            <Text style={[styles.badgeText, { color: colours.text }]}>
                {getSeverityLabel(severity as "high" | "medium" | "low")}
            </Text>
        </View>
    );
}

function ResultsSection({ result }: { result: NonNullable<ReturnType<typeof useCamera>["result"]> }) {
    const metaFindings = result.metadata?.findings ?? [];
    const sorted = sortFindingsBySeverity(metaFindings);
    const counts = countBySeverity(metaFindings);
    const detection = result.detection;

    return (
        <View style={styles.resultsContainer}>

            {/* Pipeline header */}
            <View style={styles.pipelineHeader}>
                <View style={styles.pipelineDot} />
                <Text style={styles.pipelineLabel}>Analysis Complete</Text>
                <Text style={styles.pipelineStatus}>{result.status.toUpperCase()}</Text>
            </View>

            {/* Detection summary */}
            {detection && (
                <View style={styles.section}>
                    <Text style={styles.sectionTitle}>Detection</Text>
                    <View style={styles.pillRow}>
                        <DetectionPill label="Faces" count={detection.face_count} colour="#FF6B6B" />
                        <DetectionPill label="QR Codes" count={detection.qr_count} colour="#FFB347" />
                        <DetectionPill label="Text" count={detection.text_count} colour="#94A3B8" />
                    </View>
                </View>
            )}

            {/* Metadata findings */}
            <View style={styles.section}>
                <View style={styles.sectionHeaderRow}>
                    <Text style={styles.sectionTitle}>Metadata</Text>
                    {metaFindings.length > 0 && (
                        <Text style={styles.findingCount}>{metaFindings.length} concern{metaFindings.length !== 1 ? "s" : ""}</Text>
                    )}
                </View>

                {metaFindings.length === 0 && result.metadata?.extraction_success && (
                    <View style={styles.cleanBox}>
                        <Text style={styles.cleanText}>✓ No metadata concerns found.</Text>
                    </View>
                )}

                {!result.metadata?.extraction_success && (
                    <View style={styles.warningBox}>
                        <Text style={styles.warningText}>Metadata could not be read.</Text>
                    </View>
                )}

                {sorted.map((finding, i) => (
                    <View key={`${finding.field_name}-${i}`} style={styles.findingRow}>
                        <View style={styles.findingHeader}>
                            <SeverityBadge severity={finding.severity} />
                            <Text style={styles.findingCategory}>{getCategoryLabel(finding.category)}</Text>
                        </View>
                        <Text style={styles.findingValue} numberOfLines={2}>{finding.value}</Text>
                        <Text style={styles.findingExplanation}>{finding.explanation}</Text>
                    </View>
                ))}
            </View>
        </View>
    );
}

function DetectionPill({ label, count, colour }: { label: string; count: number; colour: string }) {
    return (
        <View style={styles.detectionPill}>
            <Text style={[styles.pillCount, { color: count > 0 ? colour : "#475569" }]}>{count}</Text>
            <Text style={styles.pillLabel}>{label}</Text>
        </View>
    );
}


// ─────────────────────────────────────────────────────────────────
// MAIN COMPONENT
// ─────────────────────────────────────────────────────────────────

export function PrivoCameraView() {
    const {
        screenState,
        facing,
        capturedUri,
        result,
        error,
        cameraRef,
        requestPermission,
        handleFlipCamera,
        handleCapture,
        handleRetake,
        handleAnalyze,
        handleReset,
    } = useCamera();

    return (
        <SafeAreaView style={styles.safeArea}>

            {/* ── PERMISSION SCREEN ──────────────────────────────── */}
            {screenState === "permissions" && (
                <PermissionScreen onRequest={requestPermission} />
            )}

            {/* ── ERROR SCREEN ───────────────────────────────────── */}
            {screenState === "error" && (
                <ErrorScreen message={error ?? "An error occurred."} onRetry={handleReset} />
            )}

            {/* ── VIEWFINDER ─────────────────────────────────────── */}
            {screenState === "viewfinder" && (
                <View style={styles.viewfinderContainer}>
                    <ExpoCameraView
                        ref={cameraRef}
                        style={styles.viewfinder}
                        facing={facing}
                    />
                    {/* Controls overlay */}
                    <View style={styles.cameraControls}>
                        <TouchableOpacity style={styles.flipButton} onPress={handleFlipCamera} activeOpacity={0.7}>
                            <Text style={styles.flipIcon}>🔄</Text>
                        </TouchableOpacity>
                        <TouchableOpacity style={styles.captureButton} onPress={handleCapture} activeOpacity={0.8}>
                            <View style={styles.captureInner} />
                        </TouchableOpacity>
                        <View style={styles.flipButton} />
                        {/* Empty view balances the flip button for centering */}
                    </View>
                </View>
            )}

            {/* ── CAPTURED / ANALYSING / RESULT ──────────────────── */}
            {(screenState === "captured" || screenState === "analysing" || screenState === "result") && (
                <ScrollView
                    style={styles.scrollView}
                    contentContainerStyle={styles.scrollContent}
                    showsVerticalScrollIndicator={false}
                >
                    {/* Frozen preview */}
                    {capturedUri && (
                        <Image
                            source={{ uri: capturedUri }}
                            style={styles.capturedImage}
                            resizeMode="contain"
                        />
                    )}

                    {/* Captured state — action buttons */}
                    {screenState === "captured" && (
                        <View style={styles.capturedActions}>
                            <TouchableOpacity style={styles.secondaryButton} onPress={handleRetake} activeOpacity={0.7}>
                                <Text style={styles.secondaryButtonText}>Retake</Text>
                            </TouchableOpacity>
                            <TouchableOpacity style={styles.primaryButton} onPress={handleAnalyze} activeOpacity={0.8}>
                                <Text style={styles.primaryButtonText}>Analyse</Text>
                            </TouchableOpacity>
                        </View>
                    )}

                    {/* Analysing state — spinner */}
                    {screenState === "analysing" && (
                        <View style={styles.analysingRow}>
                            <ActivityIndicator size="small" color="#8B5CF6" />
                            <Text style={styles.analysingText}>Analysing image...</Text>
                        </View>
                    )}

                    {/* Result state */}
                    {screenState === "result" && result && (
                        <>
                            <ResultsSection result={result} />
                            <TouchableOpacity style={styles.resetButton} onPress={handleReset} activeOpacity={0.7}>
                                <Text style={styles.resetButtonText}>Capture Another</Text>
                            </TouchableOpacity>
                        </>
                    )}
                </ScrollView>
            )}

        </SafeAreaView>
    );
}


// ─────────────────────────────────────────────────────────────────
// STYLES
// ─────────────────────────────────────────────────────────────────

const C = {
    bg: "#020617",
    surface: "#0F172A",
    surfaceAlt: "#1E293B",
    border: "#334155",
    text: "#F1F5F9",
    textSec: "#94A3B8",
    textMuted: "#475569",
    accent: "#7C3AED",
    success: "#10B981",
    errorBg: "#1C0A0A",
    errorBorder: "#7F1D1D",
    errorText: "#FCA5A5",
    warningBg: "#1C1000",
    warningText: "#FCD34D",
};

const styles = StyleSheet.create({
    safeArea: { flex: 1, backgroundColor: C.bg },
    scrollView: { flex: 1 },
    scrollContent: {
        paddingHorizontal: 16,
        paddingBottom: 40,
        paddingTop: Platform.OS === "android" ? 12 : 0,
    },

    // Centered screens (permission, error)
    centeredScreen: {
        flex: 1, alignItems: "center", justifyContent: "center",
        paddingHorizontal: 32, gap: 16,
    },
    shieldEmoji: { fontSize: 48 },
    errorEmoji: { fontSize: 40 },
    permissionTitle: { fontSize: 18, fontWeight: "700", color: C.text, textAlign: "center" },
    permissionBody: { fontSize: 14, color: C.textSec, textAlign: "center", lineHeight: 22 },
    errorText: { fontSize: 14, color: C.errorText, textAlign: "center", lineHeight: 22 },

    // Viewfinder
    viewfinderContainer: { flex: 1 },
    viewfinder: { width: "100%", height: VIEWFINDER_HEIGHT },
    cameraControls: {
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
        paddingHorizontal: 40,
        paddingVertical: 24,
        backgroundColor: C.bg,
    },
    captureButton: {
        width: 72, height: 72, borderRadius: 36,
        borderWidth: 4, borderColor: "#FFFFFF",
        alignItems: "center", justifyContent: "center",
    },
    captureInner: {
        width: 56, height: 56, borderRadius: 28,
        backgroundColor: "#FFFFFF",
    },
    flipButton: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
    flipIcon: { fontSize: 24 },

    // Captured image
    capturedImage: { width: "100%", height: 260, backgroundColor: C.surface, marginBottom: 12 },
    capturedActions: {
        flexDirection: "row", gap: 12, marginBottom: 16,
    },
    analysingRow: {
        flexDirection: "row", alignItems: "center", justifyContent: "center",
        gap: 10, paddingVertical: 20,
    },
    analysingText: { fontSize: 14, color: C.textSec },

    // Buttons
    primaryButton: {
        flex: 1, backgroundColor: C.accent, borderRadius: 10,
        paddingVertical: 14, alignItems: "center",
    },
    primaryButtonText: { color: "#FFFFFF", fontSize: 15, fontWeight: "600" },
    secondaryButton: {
        flex: 1, borderWidth: 1, borderColor: C.border, borderRadius: 10,
        paddingVertical: 14, alignItems: "center",
    },
    secondaryButtonText: { color: C.textSec, fontSize: 15 },
    resetButton: { paddingVertical: 16, alignItems: "center", marginTop: 8 },
    resetButtonText: { color: C.textSec, fontSize: 14 },

    // Results
    resultsContainer: { gap: 12 },
    pipelineHeader: {
        flexDirection: "row", alignItems: "center",
        backgroundColor: "rgba(124,58,237,0.1)",
        borderWidth: 1, borderColor: "rgba(124,58,237,0.3)",
        borderRadius: 12, paddingHorizontal: 14, paddingVertical: 10, gap: 8,
    },
    pipelineDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: C.success },
    pipelineLabel: { flex: 1, fontSize: 14, fontWeight: "500", color: C.text },
    pipelineStatus: { fontSize: 11, fontWeight: "600", color: "#8B5CF6", letterSpacing: 0.5 },

    section: { gap: 8 },
    sectionHeaderRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
    sectionTitle: { fontSize: 15, fontWeight: "600", color: C.text },
    findingCount: { fontSize: 13, color: C.textSec },

    pillRow: { flexDirection: "row", gap: 12 },
    detectionPill: {
        alignItems: "center", backgroundColor: C.surface,
        borderRadius: 10, borderWidth: 1, borderColor: C.border,
        paddingVertical: 8, paddingHorizontal: 16, minWidth: 72,
    },
    pillCount: { fontSize: 20, fontWeight: "700" },
    pillLabel: { fontSize: 11, color: C.textSec, marginTop: 2 },

    cleanBox: {
        backgroundColor: "rgba(16,185,129,0.1)", borderRadius: 10,
        padding: 14, borderWidth: 1, borderColor: "rgba(16,185,129,0.2)",
    },
    cleanText: { fontSize: 13, color: C.success, lineHeight: 20 },
    warningBox: { backgroundColor: C.warningBg, borderRadius: 10, padding: 14 },
    warningText: { fontSize: 13, color: C.warningText, lineHeight: 20 },

    findingRow: {
        backgroundColor: C.surface, borderRadius: 12,
        borderWidth: 1, borderColor: C.border, padding: 14, gap: 6,
    },
    findingHeader: { flexDirection: "row", alignItems: "center", gap: 8, flexWrap: "wrap" },
    findingCategory: { fontSize: 13, fontWeight: "600", color: C.text, flex: 1 },
    findingValue: { fontSize: 13, color: C.text, fontWeight: "500" },
    findingExplanation: { fontSize: 12, color: C.textSec, lineHeight: 18 },

    badge: { borderRadius: 6, borderWidth: 1, paddingHorizontal: 8, paddingVertical: 3 },
    badgeText: { fontSize: 11, fontWeight: "600" },
});
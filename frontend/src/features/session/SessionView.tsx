import React from "react";
import {
    ActivityIndicator,
    Image,
    ScrollView,
    StyleSheet,
    Text,
    TouchableOpacity,
    View,
} from "react-native";

import type { AnalysisResponse } from "../../types/analysis";
import { APP_NAME } from "../../lib/constants";

/**
 * SessionView
 *
 * Displays the current Privo analysis session.
 *
 * UI responsibility:
 * - show the image being analysed
 * - show processing state
 * - show the returned analysis summary
 * - expose a retry/reset action
 *
 * Backend responsibility:
 * - creating/managing the session
 * - image analysis
 * - detection
 * - metadata extraction
 * - risk calculation
 * - protection processing
 *
 * This component intentionally does not implement backend logic.
 * The parent screen/hook can connect the real API later without
 * changing this presentation layer.
 */

export interface SessionViewProps {
    /** Image URI currently associated with the session. */
    imageUri?: string | null;

    /** Current analysis result returned by the Privo backend. */
    result?: AnalysisResponse | null;

    /** True while the backend is processing the image. */
    loading?: boolean;

    /** User-friendly error returned by the upload/session layer. */
    error?: string | null;

    /** Called when the user wants to analyse another image. */
    onReset?: () => void;

    /** Optional action for opening the detailed result screen. */
    onViewResults?: () => void;
}

export function SessionView({
    imageUri,
    result,
    loading = false,
    error = null,
    onReset,
    onViewResults,
}: SessionViewProps) {
    return (
        <ScrollView
            style={styles.container}
            contentContainerStyle={styles.content}
            showsVerticalScrollIndicator={false}
        >
            <View style={styles.header}>
                <Text style={styles.appName}>{APP_NAME}</Text>
                <Text style={styles.title}>Privacy Analysis</Text>
            </View>

            {imageUri ? (
                <View style={styles.imageCard}>
                    <Image
                        source={{ uri: imageUri }}
                        style={styles.image}
                        resizeMode="contain"
                    />
                </View>
            ) : null}

            {loading ? (
                <View style={styles.stateCard}>
                    <ActivityIndicator size="large" color={COLORS.accent} />
                    <Text style={styles.stateTitle}>Analysing image...</Text>
                    <Text style={styles.stateText}>
                        Privo is checking the available privacy signals.
                    </Text>
                </View>
            ) : null}

            {!loading && error ? (
                <View style={styles.errorCard}>
                    <Text style={styles.errorTitle}>Analysis failed</Text>
                    <Text style={styles.errorText}>{error}</Text>

                    {onReset ? (
                        <TouchableOpacity
                            style={styles.secondaryButton}
                            onPress={onReset}
                            activeOpacity={0.8}
                        >
                            <Text style={styles.secondaryButtonText}>Try Again</Text>
                        </TouchableOpacity>
                    ) : null}
                </View>
            ) : null}

            {!loading && !error && result ? (
                <View style={styles.resultCard}>
                    <Text style={styles.resultTitle}>Analysis Complete</Text>

                    <View style={styles.resultRow}>
                        <Text style={styles.label}>Risk level</Text>
                        <Text style={styles.value}>
                            {getRiskLevel(result)}
                        </Text>
                    </View>

                    <Text style={styles.resultText}>
                        Privo has completed the current analysis session. Open the detailed
                        results to review detected privacy signals and available actions.
                    </Text>

                    {onViewResults ? (
                        <TouchableOpacity
                            style={styles.primaryButton}
                            onPress={onViewResults}
                            activeOpacity={0.8}
                        >
                            <Text style={styles.primaryButtonText}>View Results</Text>
                        </TouchableOpacity>
                    ) : null}

                    {onReset ? (
                        <TouchableOpacity
                            style={styles.secondaryButton}
                            onPress={onReset}
                            activeOpacity={0.8}
                        >
                            <Text style={styles.secondaryButtonText}>
                                Analyse Another Image
                            </Text>
                        </TouchableOpacity>
                    ) : null}
                </View>
            ) : null}

            {!loading && !error && !result ? (
                <View style={styles.stateCard}>
                    <Text style={styles.stateTitle}>Ready for analysis</Text>
                    <Text style={styles.stateText}>
                        Select an image to start a Privo privacy analysis session.
                    </Text>
                </View>
            ) : null}
        </ScrollView>
    );
}

/**
 * Keeps SessionView independent from the backend's exact risk implementation.
 * When the backend schema evolves, only this adapter needs to be updated.
 */
function getRiskLevel(result: AnalysisResponse): string {
    const candidate = result as AnalysisResponse & {
        risk_level?: string;
        risk?: { level?: string };
    };

    return (
        candidate.risk_level ??
        candidate.risk?.level ??
        "Pending"
    );
}

const COLORS = {
    background: "#020617",
    surface: "#0F172A",
    border: "#334155",
    textPrimary: "#F1F5F9",
    textSecondary: "#94A3B8",
    textMuted: "#64748B",
    accent: "#7C3AED",
    errorBackground: "#1C0A0A",
    errorBorder: "#7F1D1D",
    errorText: "#FCA5A5",
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: COLORS.background,
    },
    content: {
        padding: 16,
        paddingBottom: 40,
    },
    header: {
        paddingTop: 12,
        paddingBottom: 20,
    },
    appName: {
        color: COLORS.textMuted,
        fontSize: 13,
        fontWeight: "600",
        letterSpacing: 0.5,
    },
    title: {
        color: COLORS.textPrimary,
        fontSize: 24,
        fontWeight: "700",
        marginTop: 4,
    },
    imageCard: {
        backgroundColor: COLORS.surface,
        borderWidth: 1,
        borderColor: COLORS.border,
        borderRadius: 16,
        overflow: "hidden",
    },
    image: {
        width: "100%",
        height: 300,
        backgroundColor: COLORS.background,
    },
    stateCard: {
        alignItems: "center",
        backgroundColor: COLORS.surface,
        borderWidth: 1,
        borderColor: COLORS.border,
        borderRadius: 16,
        padding: 24,
        marginTop: 16,
    },
    stateTitle: {
        color: COLORS.textPrimary,
        fontSize: 17,
        fontWeight: "600",
        marginTop: 14,
        textAlign: "center",
    },
    stateText: {
        color: COLORS.textSecondary,
        fontSize: 13,
        lineHeight: 19,
        marginTop: 8,
        textAlign: "center",
    },
    errorCard: {
        backgroundColor: COLORS.errorBackground,
        borderWidth: 1,
        borderColor: COLORS.errorBorder,
        borderRadius: 16,
        padding: 18,
        marginTop: 16,
    },
    errorTitle: {
        color: COLORS.errorText,
        fontSize: 16,
        fontWeight: "700",
    },
    errorText: {
        color: COLORS.errorText,
        fontSize: 13,
        lineHeight: 19,
        marginTop: 8,
    },
    resultCard: {
        backgroundColor: COLORS.surface,
        borderWidth: 1,
        borderColor: COLORS.border,
        borderRadius: 16,
        padding: 18,
        marginTop: 16,
    },
    resultTitle: {
        color: COLORS.textPrimary,
        fontSize: 18,
        fontWeight: "700",
        marginBottom: 16,
    },
    resultRow: {
        flexDirection: "row",
        justifyContent: "space-between",
        alignItems: "center",
        borderBottomWidth: 1,
        borderBottomColor: COLORS.border,
        paddingBottom: 14,
    },
    label: {
        color: COLORS.textSecondary,
        fontSize: 14,
    },
    value: {
        color: COLORS.textPrimary,
        fontSize: 14,
        fontWeight: "700",
    },
    resultText: {
        color: COLORS.textSecondary,
        fontSize: 13,
        lineHeight: 19,
        marginTop: 14,
    },
    primaryButton: {
        alignItems: "center",
        backgroundColor: COLORS.accent,
        borderRadius: 10,
        paddingVertical: 14,
        marginTop: 18,
    },
    primaryButtonText: {
        color: "#FFFFFF",
        fontSize: 15,
        fontWeight: "600",
    },
    secondaryButton: {
        alignItems: "center",
        borderWidth: 1,
        borderColor: COLORS.border,
        borderRadius: 10,
        paddingVertical: 13,
        marginTop: 12,
    },
    secondaryButtonText: {
        color: COLORS.textPrimary,
        fontSize: 14,
        fontWeight: "600",
    },
});

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
} from "react-native";

import { useUpload } from "./useUpload";
import { APP_NAME, APP_TAGLINE } from "../../lib/constants";

export default function UploadZone() {
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
            <ScrollView
                style={styles.scrollView}
                contentContainerStyle={styles.content}
                showsVerticalScrollIndicator={false}
            >
                <View style={styles.header}>
                    <Text style={styles.appName}>{APP_NAME}</Text>
                    <Text style={styles.tagline}>{APP_TAGLINE}</Text>
                </View>

                {!asset && !result && (
                    <View style={styles.emptyState}>
                        <View style={styles.iconContainer}>
                            <Text style={styles.icon}>🛡️</Text>
                        </View>

                        <Text style={styles.title}>Select an image to analyse</Text>
                        <Text style={styles.subtitle}>
                            JPG, PNG, WebP, HEIC · up to 20 MB
                        </Text>

                        <TouchableOpacity
                            style={styles.primaryButton}
                            onPress={handlePickImage}
                            activeOpacity={0.8}
                        >
                            <Text style={styles.primaryButtonText}>Select Image</Text>
                        </TouchableOpacity>
                    </View>
                )}

                {asset && !result && (
                    <View style={styles.card}>
                        {previewUri && (
                            <Image
                                source={{ uri: previewUri }}
                                style={styles.preview}
                                resizeMode="contain"
                            />
                        )}

                        <View style={styles.fileInfo}>
                            <View style={styles.fileInfoText}>
                                <Text style={styles.fileName} numberOfLines={1}>
                                    {asset.fileName ?? "Selected image"}
                                </Text>
                                {!!fileSizeLabel && (
                                    <Text style={styles.fileSize}>{fileSizeLabel}</Text>
                                )}
                            </View>

                            {!loading && (
                                <TouchableOpacity
                                    onPress={handleReset}
                                    hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
                                >
                                    <Text style={styles.remove}>Remove</Text>
                                </TouchableOpacity>
                            )}
                        </View>

                        <TouchableOpacity
                            style={[styles.primaryButton, loading && styles.disabledButton]}
                            onPress={handleAnalyze}
                            disabled={loading}
                            activeOpacity={0.8}
                        >
                            {loading ? (
                                <View style={styles.loadingRow}>
                                    <ActivityIndicator size="small" color="#FFFFFF" />
                                    <Text style={styles.primaryButtonText}>  Analysing...</Text>
                                </View>
                            ) : (
                                <Text style={styles.primaryButtonText}>Analyse Image</Text>
                            )}
                        </TouchableOpacity>
                    </View>
                )}

                {error && (
                    <View style={styles.errorBox}>
                        <Text style={styles.errorTitle}>Analysis failed</Text>
                        <Text style={styles.errorText}>{error}</Text>
                        <TouchableOpacity onPress={handleReset}>
                            <Text style={styles.tryAgain}>Try another image</Text>
                        </TouchableOpacity>
                    </View>
                )}

                {result && (
                    <View style={styles.resultCard}>
                        <Text style={styles.resultTitle}>Analysis ready</Text>
                        <Text style={styles.resultText}>
                            Your image has been processed successfully.
                        </Text>

                        <TouchableOpacity
                            style={styles.primaryButton}
                            onPress={handleReset}
                            activeOpacity={0.8}
                        >
                            <Text style={styles.primaryButtonText}>Analyse Another Image</Text>
                        </TouchableOpacity>
                    </View>
                )}
            </ScrollView>
        </SafeAreaView>
    );
}

const colours = {
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
    safeArea: {
        flex: 1,
        backgroundColor: colours.background,
    },
    scrollView: {
        flex: 1,
    },
    content: {
        padding: 16,
        paddingBottom: 40,
    },
    header: {
        alignItems: "center",
        paddingVertical: 24,
    },
    appName: {
        color: colours.textPrimary,
        fontSize: 26,
        fontWeight: "700",
        letterSpacing: 0.5,
    },
    tagline: {
        color: colours.textSecondary,
        fontSize: 13,
        marginTop: 4,
    },
    emptyState: {
        alignItems: "center",
        paddingVertical: 48,
    },
    iconContainer: {
        width: 72,
        height: 72,
        borderRadius: 20,
        backgroundColor: "rgba(124,58,237,0.15)",
        alignItems: "center",
        justifyContent: "center",
        marginBottom: 20,
    },
    icon: {
        fontSize: 32,
    },
    title: {
        color: colours.textPrimary,
        fontSize: 17,
        fontWeight: "600",
        textAlign: "center",
    },
    subtitle: {
        color: colours.textMuted,
        fontSize: 13,
        textAlign: "center",
        marginTop: 8,
        marginBottom: 24,
    },
    card: {
        backgroundColor: colours.surface,
        borderRadius: 16,
        borderWidth: 1,
        borderColor: colours.border,
        overflow: "hidden",
    },
    preview: {
        width: "100%",
        height: 260,
        backgroundColor: colours.background,
    },
    fileInfo: {
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
        padding: 16,
    },
    fileInfoText: {
        flex: 1,
        marginRight: 12,
    },
    fileName: {
        color: colours.textPrimary,
        fontSize: 14,
        fontWeight: "500",
    },
    fileSize: {
        color: colours.textSecondary,
        fontSize: 12,
        marginTop: 3,
    },
    remove: {
        color: colours.textSecondary,
        fontSize: 13,
    },
    primaryButton: {
        backgroundColor: colours.accent,
        borderRadius: 10,
        paddingVertical: 14,
        alignItems: "center",
        justifyContent: "center",
        marginHorizontal: 16,
        marginBottom: 16,
    },
    disabledButton: {
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
    errorBox: {
        backgroundColor: colours.errorBackground,
        borderWidth: 1,
        borderColor: colours.errorBorder,
        borderRadius: 12,
        padding: 16,
        marginTop: 16,
    },
    errorTitle: {
        color: colours.errorText,
        fontSize: 14,
        fontWeight: "600",
        marginBottom: 6,
    },
    errorText: {
        color: colours.errorText,
        fontSize: 13,
        lineHeight: 19,
    },
    tryAgain: {
        color: colours.textPrimary,
        fontSize: 13,
        fontWeight: "600",
        marginTop: 12,
    },
    resultCard: {
        backgroundColor: colours.surface,
        borderRadius: 16,
        borderWidth: 1,
        borderColor: colours.border,
        paddingTop: 20,
        marginTop: 16,
    },
    resultTitle: {
        color: colours.textPrimary,
        fontSize: 18,
        fontWeight: "700",
        marginHorizontal: 16,
    },
    resultText: {
        color: colours.textSecondary,
        fontSize: 13,
        lineHeight: 19,
        marginTop: 8,
        marginHorizontal: 16,
        marginBottom: 20,
    },
});

/**
 * src/features/settings/ServerSettings.tsx
 *
 * Placeholder screen for the backend address. Behaviour lives in
 * useServerSettings(); this file is only layout and is meant to be replaced.
 */

import React from "react";
import {
    ActivityIndicator,
    ScrollView,
    StyleSheet,
    Text,
    TextInput,
    TouchableOpacity,
    View,
} from "react-native";
import { useServerSettings } from "./useServerSettings";

function ActionButton({
    label,
    onPress,
    disabled,
    primary = false,
}: {
    label: string;
    onPress: () => void;
    disabled: boolean;
    primary?: boolean;
}) {
    return (
        <TouchableOpacity
            style={[
                styles.button,
                primary ? styles.buttonPrimary : styles.buttonSecondary,
                disabled && styles.buttonDisabled,
            ]}
            onPress={onPress}
            disabled={disabled}
            activeOpacity={0.8}
            accessibilityRole="button"
            accessibilityState={{ disabled }}
        >
            <Text style={styles.buttonText}>{label}</Text>
        </TouchableOpacity>
    );
}

export function ServerSettings() {
    const s = useServerSettings();
    const busy = s.loading || s.saving;
    const usingDefault = s.savedUrl === null;

    return (
        <ScrollView
            style={styles.screen}
            contentContainerStyle={styles.content}
            keyboardShouldPersistTaps="handled"
        >
            <Text style={styles.title}>Server address</Text>
            <Text style={styles.body}>
                The Privo backend this app sends images to. Use your laptop's Wi-Fi IPv4
                address (run ipconfig), with the backend started using --host 0.0.0.0.
            </Text>

            <Text style={styles.label}>Currently using</Text>
            <Text style={styles.value}>
                {s.effectiveUrl}
                {usingDefault ? "  (default)" : ""}
            </Text>

            <Text style={styles.label}>New address</Text>
            <TextInput
                value={s.input}
                onChangeText={s.setInput}
                editable={!busy}
                placeholder="e.g. 192.168.1.7:8000"
                placeholderTextColor="#475569"
                autoCapitalize="none"
                autoCorrect={false}
                spellCheck={false}
                keyboardType="url"
                style={styles.input}
            />
            {s.validationError ? <Text style={styles.error}>{s.validationError}</Text> : null}

            <View style={styles.row}>
                <ActionButton
                    label="Test"
                    onPress={s.testConnection}
                    disabled={busy || !s.normalizedInput || s.test.status === "testing"}
                />
                <ActionButton
                    label={s.saving ? "Saving…" : "Save"}
                    onPress={s.save}
                    disabled={busy || !s.isDirty}
                    primary
                />
            </View>

            {s.test.status === "testing" ? (
                <View style={styles.testRow}>
                    <ActivityIndicator size="small" color="#8B5CF6" />
                    <Text style={styles.body}>Testing connection…</Text>
                </View>
            ) : null}
            {s.test.status === "ok" ? (
                <Text style={styles.ok}>
                    Connected to Privo backend{s.test.version ? ` v${s.test.version}` : ""} at {s.test.url}
                </Text>
            ) : null}
            {s.test.status === "failed" ? <Text style={styles.error}>{s.test.reason}</Text> : null}
            {s.saveError ? <Text style={styles.error}>{s.saveError}</Text> : null}

            <ActionButton label="Reset to default" onPress={s.reset} disabled={busy || usingDefault} />
        </ScrollView>
    );
}

const styles = StyleSheet.create({
    screen: { flex: 1, backgroundColor: "#020617" },
    content: { padding: 16, paddingTop: 24, gap: 10 },
    title: { fontSize: 20, fontWeight: "700", color: "#F1F5F9" },
    body: { fontSize: 13, color: "#94A3B8", lineHeight: 19 },
    label: { fontSize: 12, color: "#64748B", marginTop: 8 },
    value: { fontSize: 14, color: "#F1F5F9", fontFamily: "monospace" },
    input: {
        borderWidth: 1,
        borderColor: "#334155",
        borderRadius: 10,
        backgroundColor: "#0F172A",
        color: "#F1F5F9",
        paddingHorizontal: 12,
        paddingVertical: 10,
        fontSize: 15,
    },
    row: { flexDirection: "row", gap: 10, marginTop: 4 },
    button: { flex: 1, borderRadius: 10, paddingVertical: 13, alignItems: "center", borderWidth: 1 },
    buttonPrimary: { backgroundColor: "#7C3AED", borderColor: "#7C3AED" },
    buttonSecondary: { backgroundColor: "transparent", borderColor: "#334155" },
    buttonDisabled: { opacity: 0.4 },
    buttonText: { color: "#FFFFFF", fontSize: 14, fontWeight: "600" },
    testRow: { flexDirection: "row", alignItems: "center", gap: 8 },
    ok: { fontSize: 13, color: "#4ADE80", lineHeight: 19 },
    error: { fontSize: 13, color: "#FCA5A5", lineHeight: 19 },
});
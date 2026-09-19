import React from "react";
import { View, Text, StyleSheet } from "react-native";

type BadgeVariant = "high" | "medium" | "low" | "critical" | "info";

interface StatusBadgeProps {
    label: string;
    variant: BadgeVariant;
}

const COLOURS: Record<BadgeVariant, { bg: string; text: string; border: string }> = {
    critical: { bg: "#1A0000", text: "#FF2020", border: "#5C0000" },
    high: { bg: "#3B0000", text: "#FF6B6B", border: "#7F0000" },
    medium: { bg: "#2D1B00", text: "#FFB347", border: "#7A4500" },
    low: { bg: "#0F172A", text: "#94A3B8", border: "#1E293B" },
    info: { bg: "rgba(124,58,237,0.15)", text: "#A78BFA", border: "rgba(124,58,237,0.3)" },
};

export function StatusBadge({ label, variant }: StatusBadgeProps) {
    const c = COLOURS[variant] ?? COLOURS.low;
    return (
        <View style={[
            styles.badge,
            { backgroundColor: c.bg, borderColor: c.border }
        ]}>
            <Text style={[styles.label, { color: c.text }]}>{label}</Text>
        </View>
    );
}

const styles = StyleSheet.create({
    badge: {
        borderRadius: 6,
        borderWidth: 1,
        paddingHorizontal: 8,
        paddingVertical: 3,
        alignSelf: "flex-start",
    },
    label: {
        fontSize: 11,
        fontWeight: "600",
    },
});

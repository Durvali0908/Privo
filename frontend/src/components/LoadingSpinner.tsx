import React from "react";
import { View, ActivityIndicator, Text, StyleSheet } from "react-native";

interface LoadingSpinnerProps {
    label?: string;
    size?: "small" | "large";
    color?: string;
}

export function LoadingSpinner({
    label,
    size = "small",
    color = "#8B5CF6",
}: LoadingSpinnerProps) {
    return (
        <View style={styles.container}>
            <ActivityIndicator size={size} color={color} />
            {label && <Text style={styles.label}>{label}</Text>}
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "center",
        gap: 10,
        paddingVertical: 16,
    },
    label: {
        fontSize: 14,
        color: "#94A3B8",
    },
});

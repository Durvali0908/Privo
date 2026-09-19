import React from "react";
import { View, StyleSheet, ViewStyle } from "react-native";

interface CardProps {
    children: React.ReactNode;
    style?: ViewStyle;
    variant?: "default" | "accent" | "warning" | "danger" | "success";
}

export function Card({ children, style, variant = "default" }: CardProps) {
    return (
        <View style={[styles.base, styles[variant], style]}>
            {children}
        </View>
    );
}

const styles = StyleSheet.create({
    base: {
        borderRadius: 12,
        borderWidth: 1,
        padding: 14,
        backgroundColor: "#0F172A",
        borderColor: "#334155",
    },
    default: {},
    accent: {
        backgroundColor: "rgba(124,58,237,0.08)",
        borderColor: "rgba(124,58,237,0.3)",
    },
    warning: {
        backgroundColor: "#1C1000",
        borderColor: "#7A4500",
    },
    danger: {
        backgroundColor: "#1C0A0A",
        borderColor: "#7F1D1D",
    },
    success: {
        backgroundColor: "rgba(16,185,129,0.08)",
        borderColor: "rgba(16,185,129,0.2)",
    },
});

import React from "react";
import {
    TouchableOpacity,
    Text,
    ActivityIndicator,
    StyleSheet,
    ViewStyle,
    TextStyle,
} from "react-native";

interface ButtonProps {
    label: string;
    onPress: () => void;
    variant?: "primary" | "secondary" | "danger";
    loading?: boolean;
    disabled?: boolean;
    style?: ViewStyle;
    textStyle?: TextStyle;
}

export function Button({
    label,
    onPress,
    variant = "primary",
    loading = false,
    disabled = false,
    style,
    textStyle,
}: ButtonProps) {
    const isDisabled = disabled || loading;

    return (
        <TouchableOpacity
            style={[
                styles.base,
                styles[variant],
                isDisabled && styles.disabled,
                style,
            ]}
            onPress={onPress}
            disabled={isDisabled}
            activeOpacity={0.8}
        >
            {loading ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
            ) : (
                <Text style={[styles.label, styles[`${variant}Label` as keyof typeof styles], textStyle]}>
                    {label}
                </Text>
            )}
        </TouchableOpacity>
    );
}

const styles = StyleSheet.create({
    base: {
        borderRadius: 10,
        paddingVertical: 14,
        paddingHorizontal: 20,
        alignItems: "center",
        justifyContent: "center",
        minHeight: 48,
    },
    primary: { backgroundColor: "#7C3AED" },
    secondary: { borderWidth: 1, borderColor: "#334155", backgroundColor: "transparent" },
    danger: { backgroundColor: "#7F0000" },
    disabled: { opacity: 0.5 },
    label: { fontSize: 15, fontWeight: "600" },
    primaryLabel: { color: "#FFFFFF" },
    secondaryLabel: { color: "#94A3B8" },
    dangerLabel: { color: "#FCA5A5" },
});

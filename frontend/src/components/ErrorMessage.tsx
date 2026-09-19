import React from "react";
import { View, Text, StyleSheet } from "react-native";

interface ErrorMessageProps {
    message: string;
}

export function ErrorMessage({ message }: ErrorMessageProps) {
    return (
        <View style={styles.container} accessibilityRole="alert">
            <Text style={styles.icon}>⚠️</Text>
            <Text style={styles.message}>{message}</Text>
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flexDirection: "row",
        alignItems: "flex-start",
        backgroundColor: "#1C0A0A",
        borderWidth: 1,
        borderColor: "#7F1D1D",
        borderRadius: 12,
        padding: 14,
        gap: 10,
    },
    icon: {
        fontSize: 16,
        marginTop: 1,
    },
    message: {
        flex: 1,
        fontSize: 13,
        color: "#FCA5A5",
        lineHeight: 20,
    },
});

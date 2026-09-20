/**
 * src/features/protection/HeatmapOverlay.tsx
 *
 * Renders semi-transparent coloured overlays on top of the
 * captured/selected image, visualising privacy-sensitive regions.
 *
 * Each HeatmapCell from the backend is rendered as an absolutely
 * positioned View with opacity driven by cell.intensity.
 *
 * Coordinate scaling:
 *   The backend produces pixel coordinates relative to the source image
 *   (image_width × image_height). The displayed image is scaled to fit
 *   the screen. We scale each cell proportionally:
 *
 *   screen_x = (cell.x / image_width)  * display_width
 *   screen_y = (cell.y / image_height) * display_height
 */

import React from "react";
import { View, StyleSheet } from "react-native";
import type { HeatmapData, HeatmapCell } from "../../types/analysis";

interface HeatmapOverlayProps {
    heatmap: HeatmapData;
    displayWidth: number;    // rendered image width in screen pixels
    displayHeight: number;    // rendered image height in screen pixels
}

function hexToRgba(hex: string, opacity: number): string {
    const h = hex.replace("#", "");
    const r = parseInt(h.substring(0, 2), 16);
    const g = parseInt(h.substring(2, 4), 16);
    const b = parseInt(h.substring(4, 6), 16);
    return `rgba(${r},${g},${b},${opacity})`;
}

function Cell({
    cell,
    scaleX,
    scaleY,
}: {
    cell: HeatmapCell;
    scaleX: number;
    scaleY: number;
}) {
    const left = cell.x * scaleX;
    const top = cell.y * scaleY;
    const width = cell.width * scaleX;
    const height = cell.height * scaleY;

    // Minimum visible size — very small text regions collapse on mobile
    if (width < 4 || height < 4) return null;

    const bgColour = hexToRgba(cell.colour, cell.intensity * 0.45);
    const borderColour = hexToRgba(cell.colour, cell.intensity * 0.85);

    return (
        <View
            style={[
                styles.cell,
                {
                    left,
                    top,
                    width,
                    height,
                    backgroundColor: bgColour,
                    borderColor: borderColour,
                },
            ]}
        />
    );
}

export function HeatmapOverlay({
    heatmap,
    displayWidth,
    displayHeight,
}: HeatmapOverlayProps) {
    if (!heatmap.success || heatmap.cells.length === 0) return null;
    if (!heatmap.image_width || !heatmap.image_height) return null;

    const scaleX = displayWidth / heatmap.image_width;
    const scaleY = displayHeight / heatmap.image_height;

    return (
        <View
            style={[styles.overlay, { width: displayWidth, height: displayHeight }]}
            pointerEvents="none"
        // pointerEvents="none": overlay is purely visual.
        // Touch events pass through to any buttons beneath it.
        >
            {heatmap.cells.map((cell, i) => (
                <Cell key={`cell-${i}`} cell={cell} scaleX={scaleX} scaleY={scaleY} />
            ))}
        </View>
    );
}

const styles = StyleSheet.create({
    overlay: {
        position: "absolute",
        top: 0,
        left: 0,
    },
    cell: {
        position: "absolute",
        borderWidth: 1,
        borderRadius: 3,
    },
});

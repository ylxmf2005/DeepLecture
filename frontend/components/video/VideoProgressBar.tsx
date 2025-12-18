"use client";

import { VideoSeekSlider } from "react-video-seek-slider";
import "react-video-seek-slider/styles.css";

interface VideoProgressBarProps {
    currentTime: number;
    duration: number;
    onSeek: (time: number) => void;
    bufferTime?: number;
    className?: string;
}

export function VideoProgressBar({
    currentTime,
    duration,
    onSeek,
    bufferTime,
    className,
}: VideoProgressBarProps) {
    const durationMs = Number.isFinite(duration) && duration > 0 ? duration * 1000 : 0;
    const currentTimeMs = Number.isFinite(currentTime)
        ? Math.min(Math.max(0, currentTime * 1000), durationMs)
        : 0;
    const bufferTimeMs = bufferTime !== undefined && Number.isFinite(bufferTime)
        ? Math.max(0, bufferTime * 1000)
        : undefined;

    if (durationMs <= 0) {
        return (
            <div className={`w-full h-1 bg-white/30 rounded-full ${className ?? ""}`} />
        );
    }

    return (
        <div className={`video-progress-bar-wrapper w-full overflow-visible ${className ?? ""}`}>
            <VideoSeekSlider
                max={durationMs}
                currentTime={currentTimeMs}
                bufferTime={bufferTimeMs}
                onChange={(timeMs: number) => onSeek(timeMs / 1000)}
                limitTimeTooltipBySides
            />
        </div>
    );
}

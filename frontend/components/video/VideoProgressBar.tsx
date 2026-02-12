"use client";

import { VideoSeekSlider } from "react-video-seek-slider";
import "react-video-seek-slider/styles.css";

interface VideoProgressBarProps {
    currentTime: number;
    duration: number;
    onSeek: (time: number) => void;
    bufferTime?: number;
    className?: string;
    /** Bookmark timestamps to display as dots on the progress bar */
    bookmarkTimestamps?: number[];
}

export function VideoProgressBar({
    currentTime,
    duration,
    onSeek,
    bufferTime,
    className,
    bookmarkTimestamps,
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
        <div className={`video-progress-bar-wrapper w-full overflow-visible relative ${className ?? ""}`}>
            <VideoSeekSlider
                max={durationMs}
                currentTime={currentTimeMs}
                bufferTime={bufferTimeMs}
                onChange={(timeMs: number) => onSeek(timeMs / 1000)}
                limitTimeTooltipBySides
            />
            {bookmarkTimestamps && bookmarkTimestamps.length > 0 && duration > 0 && (
                <div className="absolute inset-0 pointer-events-none">
                    {bookmarkTimestamps.map((ts, i) => (
                        <div
                            key={i}
                            className="absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-yellow-400 border border-yellow-600"
                            style={{ left: `${(ts / duration) * 100}%` }}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}

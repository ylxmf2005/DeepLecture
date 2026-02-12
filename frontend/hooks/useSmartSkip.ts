"use client";

import { useCallback, useMemo, useRef } from "react";
import type { VideoPlayerRef } from "@/components/video/VideoPlayer";
import type { TimelineEntry } from "@/lib/api";

/**
 * Small tolerance (in seconds) when comparing playback time against
 * timeline entry boundaries to account for keyframe-based seeking and
 * floating-point rounding.
 */
export const SMART_SKIP_EPS = 0.25;

/**
 * Binary search to check whether `time` falls within any kept entry.
 * Entries MUST be sorted by `start` ascending.
 */
function isInKeptEntry(time: number, entries: TimelineEntry[]): boolean {
    let lo = 0;
    let hi = entries.length - 1;

    while (lo <= hi) {
        const mid = (lo + hi) >>> 1;
        const entry = entries[mid];

        if (time < entry.start - SMART_SKIP_EPS) {
            hi = mid - 1;
        } else if (time >= entry.end) {
            lo = mid + 1;
        } else {
            // entry.start - EPS <= time < entry.end
            return true;
        }
    }
    return false;
}

/**
 * Binary search for the first entry whose start is > threshold.
 * Entries MUST be sorted by `start` ascending.
 */
function findNextEntry(threshold: number, entries: TimelineEntry[]): TimelineEntry | undefined {
    let lo = 0;
    let hi = entries.length;

    while (lo < hi) {
        const mid = (lo + hi) >>> 1;
        if (entries[mid].start > threshold) {
            hi = mid;
        } else {
            lo = mid + 1;
        }
    }
    return lo < entries.length ? entries[lo] : undefined;
}

export interface UseSmartSkipOptions {
    playerRef: React.RefObject<VideoPlayerRef | null>;
    skipRamblingEnabled: boolean;
    timelineEntries: TimelineEntry[];
    setCurrentTime: (time: number) => void;
}

export interface UseSmartSkipReturn {
    /** Ref tracking the current skip target (null if no skip in progress) */
    lastSkipTargetRef: React.MutableRefObject<number | null>;
    /**
     * Check if a skip should be triggered at the given time.
     * Returns true if a skip was triggered or is in progress.
     */
    handleSmartSkipCheck: (time: number) => boolean;
    /**
     * Handle a manual seek, setting up the skip target guard when Smart Skip is enabled.
     */
    handleSeek: (time: number) => void;
}

/**
 * Hook to manage Smart Skip functionality for skipping rambling sections.
 *
 * Smart Skip automatically advances playback when the current time falls
 * outside any "kept" timeline entry, seeking to the next kept entry.
 */
export function useSmartSkip({
    playerRef,
    skipRamblingEnabled,
    timelineEntries,
    setCurrentTime,
}: UseSmartSkipOptions): UseSmartSkipReturn {
    const lastSkipTargetRef = useRef<number | null>(null);

    // Ensure entries are sorted by start time for binary search.
    const sortedEntries = useMemo(() => {
        const copy = [...timelineEntries];
        copy.sort((a, b) => a.start - b.start);
        return copy;
    }, [timelineEntries]);

    const handleSmartSkipCheck = useCallback(
        (time: number): boolean => {
            if (!skipRamblingEnabled || sortedEntries.length === 0) {
                return false; // No skip, allow normal UI update
            }

            const target = lastSkipTargetRef.current;

            if (target !== null) {
                // A skip (either automatic or user-initiated) is in progress.
                // Only clear the target once we've actually entered a kept
                // timeline entry, allowing for a small epsilon around the start
                // time to account for keyframe-based seeking.
                const inKeptAfterSkip = isInKeptEntry(time, sortedEntries);

                if (!inKeptAfterSkip) {
                    // Still skipping, update time but signal skip in progress
                    setCurrentTime(time);
                    return true;
                }

                lastSkipTargetRef.current = null;
            }

            const inKept = isInKeptEntry(time, sortedEntries);

            if (!inKept) {
                const nextEntry = findNextEntry(time + SMART_SKIP_EPS, sortedEntries);
                if (nextEntry) {
                    lastSkipTargetRef.current = nextEntry.start;
                    playerRef.current?.seekTo(nextEntry.start);
                    return true; // Skip triggered
                }
            }

            return false; // No skip, allow normal UI update
        },
        [skipRamblingEnabled, sortedEntries, setCurrentTime, playerRef]
    );

    const handleSeek = useCallback(
        (time: number) => {
            // Treat a manual seek as a one-off Smart Skip target when the
            // feature is enabled so that the first few time updates after
            // the seek go through the same "skip in progress" guard and
            // do not immediately trigger another jump.
            lastSkipTargetRef.current = skipRamblingEnabled ? time : null;
            playerRef.current?.seekTo(time);
        },
        [skipRamblingEnabled, playerRef]
    );

    return {
        lastSkipTargetRef,
        handleSmartSkipCheck,
        handleSeek,
    };
}

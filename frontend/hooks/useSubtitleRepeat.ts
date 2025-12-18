"use client";

import { useCallback, useRef } from "react";
import type { VideoPlayerRef } from "@/components/video/VideoPlayer";
import type { Subtitle } from "@/lib/srt";
import { findSubtitleAtTime, binarySearchSubtitle } from "@/lib/subtitleSearch";

export interface UseSubtitleRepeatOptions {
    playerRef: React.RefObject<VideoPlayerRef | null>;
    subtitles: Subtitle[];
    subtitleRepeatCount: number;
    /** Base time update handler to call after repeat logic */
    onBaseTimeUpdate: (time: number) => void;
}

export interface UseSubtitleRepeatReturn {
    /** Handle time updates with subtitle repeat logic */
    handleTimeUpdate: (time: number) => void;
    /** Reset repeat state (call when video/subtitles change) */
    resetRepeatState: () => void;
}

/**
 * Hook to manage subtitle repeat functionality.
 *
 * When subtitleRepeatCount > 1, automatically seeks back to the start
 * of a subtitle cue when it ends, repeating it the specified number of times.
 */
export function useSubtitleRepeat({
    playerRef,
    subtitles,
    subtitleRepeatCount,
    onBaseTimeUpdate,
}: UseSubtitleRepeatOptions): UseSubtitleRepeatReturn {
    // State for tracking repeat progress
    const subtitleRepeatStateRef = useRef<{ key: string | null; count: number }>({
        key: null,
        count: 0,
    });
    const lastSubtitleIndexRef = useRef<number>(-1);
    const lastTimeRef = useRef(0);
    const lastSubtitleRef = useRef<Subtitle | null>(null);
    const repeatSeekTargetRef = useRef<number | null>(null);

    const resetRepeatState = useCallback(() => {
        subtitleRepeatStateRef.current = { key: null, count: 0 };
        lastSubtitleRef.current = null;
        lastSubtitleIndexRef.current = -1;
        repeatSeekTargetRef.current = null;
        lastTimeRef.current = 0;
    }, []);

    const handleTimeUpdate = useCallback(
        (time: number) => {
            const hasSubs = subtitles && subtitles.length > 0;
            const shouldRepeat = subtitleRepeatCount > 1 && hasSubs;

            if (!shouldRepeat) {
                subtitleRepeatStateRef.current = { key: null, count: 0 };
                repeatSeekTargetRef.current = null;
                lastTimeRef.current = time;
                lastSubtitleRef.current = null;
                onBaseTimeUpdate(time);
                return;
            }

            const prevTime = lastTimeRef.current;
            const target = repeatSeekTargetRef.current;
            const eps = 0.05; // Error tolerance: 50 ms
            const repeatWindow = 0.3; // Repeat-seek capture window: 300 ms
            const seekWindow = 1.0; // Treat jumps beyond 1 s as manual seek

            const movedBackward = time + eps < prevTime;
            const jump = Math.abs(time - prevTime);
            const hasPendingRepeat = target !== null;
            const nearTarget = hasPendingRepeat && Math.abs(time - target) < repeatWindow;
            const fromRepeatSeek = hasPendingRepeat && (movedBackward || nearTarget);
            const manualSeek = !fromRepeatSeek && jump > seekWindow;

            if (manualSeek) {
                // Large manual jump: reset repeat state to avoid wrong rewind
                subtitleRepeatStateRef.current = { key: null, count: 0 };
                repeatSeekTargetRef.current = null;
                lastTimeRef.current = time;
                lastSubtitleRef.current = null;
                onBaseTimeUpdate(time);
                return;
            }

            if (movedBackward && !fromRepeatSeek) {
                // User dragged backward: clear repeat state
                subtitleRepeatStateRef.current = { key: null, count: 0 };
            }

            if (fromRepeatSeek) {
                // Repeat seek we triggered ourselves: clear pending marker
                repeatSeekTargetRef.current = null;
            }

            // Gap-fill semantics for repeat: keep the last cue active until the next cue starts.
            const curSub = hasSubs ? findSubtitleAtTime(time, subtitles) : null;
            const prevSub = lastSubtitleRef.current;

            if (!curSub && !prevSub) {
                subtitleRepeatStateRef.current = { key: null, count: 0 };
                lastTimeRef.current = time;
                lastSubtitleRef.current = null;
                onBaseTimeUpdate(time);
                return;
            }

            // Use the previous frame's subtitle as the primary detector
            const activeSub = prevSub || curSub;

            if (!activeSub) {
                subtitleRepeatStateRef.current = { key: null, count: 0 };
                lastTimeRef.current = time;
                lastSubtitleRef.current = curSub;
                onBaseTimeUpdate(time);
                return;
            }

            // Avoid O(n) indexOf on each timeupdate.
            // Prefer cached index; fall back to binary search by time.
            let idx = lastSubtitleIndexRef.current;
            if (idx < 0 || subtitles[idx] !== activeSub) {
                idx = binarySearchSubtitle(subtitles, activeSub.startTime + 1e-6);
                if (idx < 0) {
                    subtitleRepeatStateRef.current = { key: null, count: 0 };
                    lastTimeRef.current = time;
                    lastSubtitleRef.current = curSub;
                    lastSubtitleIndexRef.current = -1;
                    onBaseTimeUpdate(time);
                    return;
                }
            }
            lastSubtitleIndexRef.current = idx;

            const key = `${idx}-${activeSub.startTime}-${activeSub.endTime}`;
            const state = subtitleRepeatStateRef.current;
            const sameKey = state.key === key;
            const currentCount = sameKey ? state.count : 0;

            if (!sameKey && !hasPendingRepeat) {
                subtitleRepeatStateRef.current = { key, count: 0 };
            }

            const endThreshold = activeSub.endTime - eps;

            // Key improvement: only treat it as crossing the end when the previous frame was inside the cue
            const wasInsidePrev = prevSub
                ? prevTime >= prevSub.startTime && prevTime < prevSub.endTime
                : prevTime >= activeSub.startTime && prevTime < activeSub.endTime;
            const crossedEnd = wasInsidePrev && time >= endThreshold;

            if (crossedEnd) {
                const nextCount = currentCount + 1;

                if (nextCount < subtitleRepeatCount) {
                    subtitleRepeatStateRef.current = { key, count: nextCount };
                    repeatSeekTargetRef.current = activeSub.startTime;
                    playerRef.current?.seekTo(activeSub.startTime);
                    lastTimeRef.current = time;
                    lastSubtitleRef.current = activeSub;
                    return;
                }

                subtitleRepeatStateRef.current = { key, count: nextCount };
            }

            lastTimeRef.current = time;
            lastSubtitleRef.current = curSub;
            onBaseTimeUpdate(time);
        },
        [subtitles, subtitleRepeatCount, onBaseTimeUpdate, playerRef]
    );

    return {
        handleTimeUpdate,
        resetRepeatState,
    };
}

"use client";

import { useRef, useCallback, useEffect } from "react";
import type { VideoPlayerRef } from "@/components/video/VideoPlayer";
import { useVideoStateStore, useVideoProgress as useStoredProgress } from "@/stores";

const PROGRESS_SAVE_THRESHOLD_SECONDS = 1;
export const RESUME_TOLERANCE_SECONDS = 0.5;

export interface UseVideoProgressReturn {
    resumeTargetRef: React.RefObject<number | null>;
    lastPersistedProgressRef: React.RefObject<number>;
    persistProgress: (time: number) => void;
    maybePersistProgress: (time: number) => void;
}

interface UseVideoProgressParams {
    videoId: string;
    playerRef: React.RefObject<VideoPlayerRef | null>;
}

export function useVideoProgress({
    videoId,
    playerRef,
}: UseVideoProgressParams): UseVideoProgressReturn {
    const lastPersistedProgressRef = useRef(0);
    const lastAutoPersistTimestampMsRef = useRef(0);
    const lastObservedProgressRef = useRef(0);
    const resumeTargetRef = useRef<number | null>(null);

    // Get store actions
    const setProgress = useVideoStateStore((s) => s.setProgress);

    // Get stored progress from store
    const storedProgress = useStoredProgress(videoId);

    const persistProgress = useCallback((time: number) => {
        if (!videoId) return;
        const rounded = Math.max(0, Math.round(time * 1000) / 1000);
        setProgress(videoId, rounded);
    }, [videoId, setProgress]);

    const maybePersistProgress = useCallback((time: number) => {
        if (time > 0) {
            lastObservedProgressRef.current = time;
        }
        if (time < 1) return;

        // Time-based safeguard: persist at least once per second while playing
        // to avoid losing progress if unload/pagehide is skipped.
        const nowMs = Date.now();
        if (nowMs - lastAutoPersistTimestampMsRef.current >= 1000) {
            lastAutoPersistTimestampMsRef.current = nowMs;
            persistProgress(time);
            lastPersistedProgressRef.current = time;
            return;
        }

        if (Math.abs(time - lastPersistedProgressRef.current) < PROGRESS_SAVE_THRESHOLD_SECONDS) {
            return;
        }

        lastPersistedProgressRef.current = time;
        persistProgress(time);
    }, [persistProgress]);

    // Initialize resume target from stored progress on mount/videoId change
    useEffect(() => {
        if (!videoId) return;

        if (storedProgress !== null && storedProgress > 0) {
            resumeTargetRef.current = storedProgress;
            lastPersistedProgressRef.current = storedProgress;
            lastObservedProgressRef.current = storedProgress;
            return;
        }

        resumeTargetRef.current = null;
        lastPersistedProgressRef.current = 0;
        lastObservedProgressRef.current = 0;
    }, [videoId, storedProgress]);

    // Save progress on unload/navigation and cleanup.
    // `pagehide` is more reliable than beforeunload on some browsers.
    useEffect(() => {
        if (typeof window === "undefined" || !videoId) return;

        const persistOnExit = () => {
            const playerTime = playerRef.current?.getCurrentTime();
            const current = (typeof playerTime === "number" && Number.isFinite(playerTime) && playerTime > 0)
                ? playerTime
                : lastObservedProgressRef.current;

            if (current > 0) {
                persistProgress(current);
            }
        };

        window.addEventListener("beforeunload", persistOnExit);
        window.addEventListener("pagehide", persistOnExit);

        return () => {
            window.removeEventListener("beforeunload", persistOnExit);
            window.removeEventListener("pagehide", persistOnExit);
            persistOnExit();
        };
    }, [persistProgress, videoId, playerRef]);

    return {
        resumeTargetRef,
        lastPersistedProgressRef,
        persistProgress,
        maybePersistProgress,
    };
}

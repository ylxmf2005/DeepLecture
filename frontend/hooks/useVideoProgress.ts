"use client";

import { useRef, useCallback, useEffect } from "react";
import type { VideoPlayerRef } from "@/components/video/VideoPlayer";
import { useVideoStateStore, useVideoProgress as useStoredProgress } from "@/stores";

const PROGRESS_SAVE_THRESHOLD_SECONDS = 5;
export const RESUME_TOLERANCE_SECONDS = 0.5;
export const RESUME_MAX_ATTEMPTS = 3;

export interface VideoProgressState {
    resumeTarget: number | null;
}

export interface VideoProgressActions {
    persistProgress: (time: number) => void;
    clearProgress: () => void;
    maybePersistProgress: (time: number) => void;
    getResumeTarget: () => number | null;
    markResumeAttempt: () => number;
    resetResumeTarget: () => void;
}

export interface UseVideoProgressReturn extends VideoProgressActions {
    resumeTargetRef: React.RefObject<number | null>;
    resumeAttemptsRef: React.RefObject<number>;
    lastPersistedProgressRef: React.RefObject<number>;
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
    const resumeTargetRef = useRef<number | null>(null);
    const resumeAttemptsRef = useRef(0);

    // Get store actions
    const setProgress = useVideoStateStore((s) => s.setProgress);
    const clearProgressStore = useVideoStateStore((s) => s.clearProgress);

    // Get stored progress from store
    const storedProgress = useStoredProgress(videoId);

    const persistProgress = useCallback((time: number) => {
        if (!videoId) return;
        const rounded = Math.max(0, Math.round(time * 1000) / 1000);
        setProgress(videoId, rounded);
    }, [videoId, setProgress]);

    const clearProgress = useCallback(() => {
        if (!videoId) return;
        clearProgressStore(videoId);
    }, [videoId, clearProgressStore]);

    const maybePersistProgress = useCallback((time: number) => {
        if (time < 1) return;
        if (Math.abs(time - lastPersistedProgressRef.current) < PROGRESS_SAVE_THRESHOLD_SECONDS) {
            return;
        }
        lastPersistedProgressRef.current = time;
        persistProgress(time);
    }, [persistProgress]);

    const getResumeTarget = useCallback(() => {
        return resumeTargetRef.current;
    }, []);

    const markResumeAttempt = useCallback(() => {
        resumeAttemptsRef.current += 1;
        return resumeAttemptsRef.current;
    }, []);

    const resetResumeTarget = useCallback(() => {
        resumeTargetRef.current = null;
        resumeAttemptsRef.current = 0;
    }, []);

    // Initialize resume target from stored progress on mount/videoId change
    useEffect(() => {
        if (!videoId) return;

        if (storedProgress !== null && storedProgress > 0) {
            resumeTargetRef.current = storedProgress;
            lastPersistedProgressRef.current = storedProgress;
        } else {
            resumeTargetRef.current = null;
            lastPersistedProgressRef.current = 0;
        }
        resumeAttemptsRef.current = 0;
    }, [videoId, storedProgress]);

    // Save progress on beforeunload and cleanup
    useEffect(() => {
        if (typeof window === "undefined" || !videoId) return;

        const handleBeforeUnload = () => {
            const current = playerRef.current?.getCurrentTime() ?? lastPersistedProgressRef.current;
            if (current > 0) {
                persistProgress(current);
            }
        };

        window.addEventListener("beforeunload", handleBeforeUnload);

        return () => {
            window.removeEventListener("beforeunload", handleBeforeUnload);
            handleBeforeUnload();
        };
    }, [persistProgress, videoId, playerRef]);

    return {
        resumeTargetRef,
        resumeAttemptsRef,
        lastPersistedProgressRef,
        persistProgress,
        clearProgress,
        maybePersistProgress,
        getResumeTarget,
        markResumeAttempt,
        resetResumeTarget,
    };
}

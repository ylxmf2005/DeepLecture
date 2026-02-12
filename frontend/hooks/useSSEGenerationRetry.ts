"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { isAPIError } from "@/lib/api";
import { toError } from "@/lib/utils/errorUtils";
import { logger } from "@/shared/infrastructure";
import { useTaskNotification } from "@/hooks/useTaskNotification";

/** Logger interface matching the scoped logger returned by logger.scope() */
type ScopedLog = ReturnType<typeof logger.scope>;

interface UseSSEGenerationRetryOptions<T> {
    /** Unique identifier for the content being loaded */
    contentId: string;
    /** SSE refresh counter — bumped by parent on task completion */
    refreshTrigger: number;
    /** Fetch the existing content. Return `null` when content doesn't exist yet. */
    fetchContent: () => Promise<T | null>;
    /** Submit the generation request. SSE will notify completion. */
    submitGeneration: () => Promise<unknown>;
    /** Scoped logger instance */
    log: ScopedLog;
    /** Extra dependency values that should trigger a re-fetch (e.g. language) */
    extraDeps?: unknown[];
    /** Canonical task type for fallback notifications when no task_id is returned */
    taskType: string;
}

interface UseSSEGenerationRetryResult<T> {
    /** Loaded content (null if not yet fetched or not found) */
    data: T | null;
    /** Whether the initial load is in progress */
    loading: boolean;
    /** Error message if load/generate failed */
    loadError: string | null;
    /** Whether a generation task is in-flight */
    isGenerating: boolean;
    /** Clear the current error */
    clearError: () => void;
    /** Trigger generation */
    handleGenerate: () => Promise<void>;
}

const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 1000;

/**
 * Shared hook for SSE-driven generation with retry logic.
 *
 * Encapsulates the pattern used by CheatsheetTab and VerifyTab:
 * 1. Fetch existing content on mount / refreshTrigger change
 * 2. When refreshTrigger changes while generating, retry up to 3 times
 *    (handles race condition where SSE arrives before file is readable)
 * 3. Provide a handleGenerate callback to submit generation requests
 */
export function useSSEGenerationRetry<T>({
    contentId,
    refreshTrigger,
    fetchContent,
    submitGeneration,
    log,
    extraDeps = [],
    taskType,
}: UseSSEGenerationRetryOptions<T>): UseSSEGenerationRetryResult<T> {
    const [data, setData] = useState<T | null>(null);
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [isGenerating, setIsGenerating] = useState(false);
    const { notifyTaskComplete } = useTaskNotification();

    // Track generating state across renders for SSE detection
    const isGeneratingRef = useRef(isGenerating);
    isGeneratingRef.current = isGenerating;

    // Track previous refreshTrigger to detect SSE notifications
    const prevRefreshTriggerRef = useRef(refreshTrigger);

    useEffect(() => {
        let cancelled = false;
        let retryCount = 0;

        const wasGenerating = isGeneratingRef.current;
        const triggerChanged = prevRefreshTriggerRef.current !== refreshTrigger;
        const isSSETriggered = triggerChanged && wasGenerating;
        prevRefreshTriggerRef.current = refreshTrigger;

        const loadData = async () => {
            try {
                setLoading(true);
                log.debug("Loading content", { contentId });
                const result = await fetchContent();
                if (cancelled) return;

                if (result !== null) {
                    setData(result);
                    setLoadError(null);
                    setIsGenerating(false);
                    log.info("Content loaded", { contentId });
                } else if (isSSETriggered && retryCount < MAX_RETRIES) {
                    retryCount++;
                    log.debug("Content not found after SSE, retrying...", { contentId });
                    setTimeout(() => {
                        if (!cancelled) loadData();
                    }, RETRY_DELAY_MS);
                    return;
                } else if (isSSETriggered) {
                    log.warn("Content not found after retries", { contentId });
                    setIsGenerating(false);
                    setLoadError("Generation completed but content not found. Please try again.");
                }
            } catch (err) {
                if (cancelled) return;
                if (isAPIError(err) && err.status === 404) {
                    if (isSSETriggered && retryCount < MAX_RETRIES) {
                        retryCount++;
                        log.debug("404 after SSE, retrying...", { contentId });
                        setTimeout(() => {
                            if (!cancelled) loadData();
                        }, RETRY_DELAY_MS);
                        return;
                    } else if (isSSETriggered) {
                        log.warn("404 after retries", { contentId });
                        setIsGenerating(false);
                        setLoadError("Generation completed but content not found. Please try again.");
                    } else {
                        log.debug("No existing content (404)", { contentId });
                    }
                } else {
                    log.error("Failed to load content", toError(err));
                    setLoadError("Failed to load content.");
                    setIsGenerating(false);
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        };

        if (contentId) {
            loadData();
        }

        return () => {
            cancelled = true;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [contentId, refreshTrigger, ...extraDeps]);

    const handleGenerate = useCallback(async () => {
        setIsGenerating(true);
        setLoadError(null);

        try {
            const response = await submitGeneration();

            const maybeTaskId = (
                typeof response === "object" &&
                response !== null &&
                "taskId" in response &&
                typeof (response as { taskId?: unknown }).taskId === "string"
            )
                ? (response as { taskId?: string }).taskId
                : undefined;
            const maybeStatus = (
                typeof response === "object" &&
                response !== null &&
                "status" in response &&
                typeof (response as { status?: unknown }).status === "string"
            )
                ? (response as { status?: string }).status
                : undefined;

            if (maybeStatus === "ready" || !maybeTaskId) {
                notifyTaskComplete(taskType, "ready");
                setIsGenerating(false);
            }
        } catch (err) {
            log.error("Failed to start generation", toError(err));
            setLoadError("Failed to start generation. Please try again.");
            setIsGenerating(false);
            notifyTaskComplete(taskType, "error", toError(err).message);
        }
    }, [submitGeneration, log, notifyTaskComplete, taskType]);

    const clearError = useCallback(() => setLoadError(null), []);

    return {
        data,
        loading,
        loadError,
        isGenerating,
        clearError,
        handleGenerate,
    };
}

"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { isAPIError } from "@/lib/api";
import { getTaskStatus, getTasksForContent } from "@/lib/api/task";
import { toError } from "@/lib/utils/errorUtils";
import { logger } from "@/shared/infrastructure";
import { useTaskNotification } from "@/hooks/useTaskNotification";
import { normalizeTaskType } from "@/lib/taskTypes";

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
const TASK_POLL_INTERVAL_MS = 1500;
const IN_FLIGHT_TASK_STATUSES = new Set(["pending", "processing"]);

function parseTaskTimestamp(task: { updatedAt?: string; createdAt?: string }): number {
    const updatedAtMs = Date.parse(task.updatedAt ?? "");
    if (!Number.isNaN(updatedAtMs)) {
        return updatedAtMs;
    }

    const createdAtMs = Date.parse(task.createdAt ?? "");
    if (!Number.isNaN(createdAtMs)) {
        return createdAtMs;
    }

    return 0;
}

function selectLatestInFlightTask(
    tasks: Array<{ id: string; type: string; status: string; updatedAt?: string; createdAt?: string }>,
    taskType: string
): { id: string; type: string; status: string; updatedAt?: string; createdAt?: string } | null {
    const canonicalType = normalizeTaskType(taskType);
    const candidates = tasks.filter(
        (task) =>
            IN_FLIGHT_TASK_STATUSES.has(task.status) &&
            normalizeTaskType(task.type) === canonicalType
    );

    if (candidates.length === 0) {
        return null;
    }

    return candidates.reduce((latest, current) => {
        return parseTaskTimestamp(current) > parseTaskTimestamp(latest) ? current : latest;
    });
}

/**
 * Shared hook for SSE-driven generation with retry logic.
 *
 * Encapsulates the pattern used by CheatsheetTab and VerifyTab:
 * 1. Fetch existing content on mount / refreshTrigger change
 * 2. When refreshTrigger changes while generating, retry up to 3 times
 *    (handles race condition where SSE arrives before file is readable)
 * 3. Poll task status as fallback when SSE updates are unavailable
 * 4. Provide a handleGenerate callback to submit generation requests
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
    const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
    const { notifyTaskComplete } = useTaskNotification();

    // Track generating state across renders for SSE detection
    const isGeneratingRef = useRef(isGenerating);
    isGeneratingRef.current = isGenerating;

    // Track previous refreshTrigger to detect SSE notifications
    const prevRefreshTriggerRef = useRef(refreshTrigger);
    const prevContentIdRef = useRef(contentId);

    // Reset generation state when content changes to avoid cross-content bleed.
    useEffect(() => {
        if (prevContentIdRef.current === contentId) {
            return;
        }
        prevContentIdRef.current = contentId;
        prevRefreshTriggerRef.current = refreshTrigger;
        setData(null);
        setLoadError(null);
        setIsGenerating(false);
        setActiveTaskId(null);
    }, [contentId, refreshTrigger]);

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
                    setActiveTaskId(null);
                    log.info("Content loaded", { contentId });
                } else if (isSSETriggered && retryCount < MAX_RETRIES) {
                    retryCount++;
                    log.debug("Content not found after SSE, retrying...", { contentId, retryCount });
                    setTimeout(() => {
                        if (!cancelled) loadData();
                    }, RETRY_DELAY_MS);
                    return;
                } else if (isSSETriggered) {
                    log.warn("Content not found after retries", { contentId });
                    setIsGenerating(false);
                    setActiveTaskId(null);
                    setLoadError("Generation completed but content not found. Please try again.");
                }
            } catch (err) {
                if (cancelled) return;
                if (isAPIError(err) && err.status === 404) {
                    if (isSSETriggered && retryCount < MAX_RETRIES) {
                        retryCount++;
                        log.debug("404 after SSE, retrying...", { contentId, retryCount });
                        setTimeout(() => {
                            if (!cancelled) loadData();
                        }, RETRY_DELAY_MS);
                        return;
                    } else if (isSSETriggered) {
                        log.warn("404 after retries", { contentId });
                        setIsGenerating(false);
                        setActiveTaskId(null);
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

    // Task polling fallback: keeps generation flows correct even when SSE drops.
    useEffect(() => {
        if (!contentId || !isGenerating || !activeTaskId) {
            return;
        }

        let cancelled = false;
        let polling = false;

        const loadAfterReady = async (): Promise<void> => {
            let retryCount = 0;

            while (!cancelled) {
                try {
                    const result = await fetchContent();
                    if (cancelled) return;

                    if (result !== null) {
                        setData(result);
                        setLoadError(null);
                        setIsGenerating(false);
                        setActiveTaskId(null);
                        return;
                    }
                } catch (err) {
                    if (cancelled) return;
                    if (!isAPIError(err) || err.status !== 404) {
                        log.error("Failed to load generated content after task completion", toError(err), { contentId, taskId: activeTaskId });
                        setLoadError("Failed to load generated content.");
                        setIsGenerating(false);
                        setActiveTaskId(null);
                        return;
                    }
                }

                if (retryCount >= MAX_RETRIES) {
                    setLoadError("Generation completed but content not found. Please try again.");
                    setIsGenerating(false);
                    setActiveTaskId(null);
                    return;
                }

                retryCount++;
                await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
            }
        };

        const pollOnce = async () => {
            if (cancelled || polling) {
                return;
            }
            polling = true;

            try {
                const task = await getTaskStatus(activeTaskId);
                if (cancelled) return;

                if (task.status === "ready") {
                    log.info("Task ready via polling fallback", { contentId, taskId: activeTaskId, taskType });
                    await loadAfterReady();
                } else if (task.status === "error") {
                    setLoadError(task.error || "Generation failed. Please try again.");
                    setIsGenerating(false);
                    setActiveTaskId(null);
                }
            } catch (err) {
                if (cancelled) return;
                // 404 can happen briefly due eventual persistence timing.
                if (isAPIError(err) && err.status === 404) {
                    log.debug("Task status not yet visible during polling", { contentId, taskId: activeTaskId });
                } else {
                    log.warn("Task polling fallback failed", {
                        contentId,
                        taskId: activeTaskId,
                        error: toError(err).message,
                    });
                }
            } finally {
                polling = false;
            }
        };

        void pollOnce();
        const interval = setInterval(() => {
            void pollOnce();
        }, TASK_POLL_INTERVAL_MS);

        return () => {
            cancelled = true;
            clearInterval(interval);
        };
    }, [activeTaskId, contentId, fetchContent, isGenerating, log, taskType]);

    // Recover in-flight state after page refresh so generation UI doesn't reset to idle.
    useEffect(() => {
        if (!contentId) {
            return;
        }

        let cancelled = false;

        const recoverInFlightTask = async () => {
            try {
                const taskList = await getTasksForContent(contentId);
                if (cancelled) return;

                const recoveredTask = selectLatestInFlightTask(taskList.tasks, taskType);
                if (!recoveredTask) {
                    return;
                }

                setIsGenerating(true);
                setActiveTaskId(recoveredTask.id);
                setLoadError(null);
                log.info("Recovered in-flight generation task", {
                    contentId,
                    taskType,
                    taskId: recoveredTask.id,
                    status: recoveredTask.status,
                });
            } catch (err) {
                if (cancelled) return;
                log.debug("Failed to recover in-flight generation task", {
                    contentId,
                    taskType,
                    error: toError(err).message,
                });
            }
        };

        void recoverInFlightTask();

        return () => {
            cancelled = true;
        };
    }, [contentId, log, taskType]);

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
                setActiveTaskId(null);
                return;
            }

            setActiveTaskId(maybeTaskId);
        } catch (err) {
            log.error("Failed to start generation", toError(err));
            setLoadError("Failed to start generation. Please try again.");
            setIsGenerating(false);
            setActiveTaskId(null);
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

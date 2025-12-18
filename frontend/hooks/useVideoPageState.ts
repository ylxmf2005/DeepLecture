"use client";

import { useState, useEffect, useRef } from "react";
import {
    ContentItem,
    getContentMetadata,
    listVoiceovers,
    getTimeline,
    TimelineEntry,
    VoiceoverEntry,
    isAPIError,
} from "@/lib/api";
import { useTaskStatus } from "@/hooks/useTaskStatus";
import { useTaskNotification } from "@/hooks/useTaskNotification";
import { useVoiceoverManagement } from "@/hooks/useVoiceoverManagement";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";
import type { AskContextItem } from "@/lib/askTypes";

const log = logger.scope("VideoPageState");

export type ProcessingAction = "generate" | "translate" | "video" | "timeline" | null;

// OCP: Task types that trigger content refresh - extend this set for new task types
const CONTENT_REFRESH_TASK_TYPES = new Set([
    "subtitle_generation",
    "subtitle_enhancement",
    "subtitle_translation",
    "timeline_generation",
    "video_generation",
    "video_merge",
    "video_import_url",
    "pdf_merge",
]);

// OCP: Subtitle tasks that force subtitle reload even when status remains `ready`
// This solves the SSE → UI refresh bug where subtitleStateKey doesn't change on regeneration
const SUBTITLE_REFRESH_TASK_TYPES = new Set([
    "subtitle_generation",
    "subtitle_enhancement",
    "subtitle_translation",
]);

// OCP: Mapping of task types to their matching processing actions
// Adding new task types only requires extending this configuration
const TASK_TO_ACTION_MAP: Record<string, ProcessingAction | ProcessingAction[]> = {
    subtitle_generation: "generate",
    timeline_generation: "timeline",
    video_generation: "video",
    video_merge: "video",           // slide lecture video merge
    video_import_url: "video",      // URL import also triggers video action
    subtitle_enhancement: "translate",
    subtitle_translation: "translate",
};

// OCP: Mapping of processingAction to content status fields for fallback polling
// This ensures fallback polling uses the same configuration as SSE handlers
// Note: "translate" action covers both translation and enhancement (both map to this action)
const ACTION_TO_STATUS_FIELDS: Record<Exclude<ProcessingAction, null>, (keyof ContentItem)[]> = {
    generate: ["subtitleStatus"],
    translate: ["translationStatus", "enhancedStatus"], // Check both - enhancement also uses "translate" action
    timeline: ["timelineStatus"],
    video: ["videoStatus"],
};

/**
 * Pure function to derive processing state from content metadata.
 * Single source of truth for determining which action is in progress.
 * Returns { processing, action, timelineLoading } based on content status fields.
 */
export function deriveProcessingState(content: ContentItem | null): {
    processing: boolean;
    action: ProcessingAction;
    timelineLoading: boolean;
} {
    if (!content) {
        return { processing: false, action: null, timelineLoading: false };
    }

    if (content.subtitleStatus === "processing") {
        return { processing: true, action: "generate", timelineLoading: false };
    }
    if (content.translationStatus === "processing" || content.enhancedStatus === "processing") {
        return { processing: true, action: "translate", timelineLoading: false };
    }
    if (content.videoStatus === "processing") {
        return { processing: true, action: "video", timelineLoading: false };
    }
    if (content.timelineStatus === "processing") {
        return { processing: true, action: "timeline", timelineLoading: true };
    }

    return { processing: false, action: null, timelineLoading: false };
}

export interface UseVideoPageStateOptions {
    videoId: string;
    /** Source language of the video - used for timeline generation */
    originalLanguage: string;
    targetLanguage: string;
    learnerProfile: string;
    /** Initial content from server component (eliminates client waterfall) */
    initialContent?: ContentItem | null;
    /** Initial voiceovers from server component (eliminates client waterfall) */
    initialVoiceovers?: VoiceoverEntry[];
}

export interface UseVideoPageStateReturn {
    // Content state
    content: ContentItem | null;
    setContent: (content: ContentItem | null) => void;
    loading: boolean;

    // Processing state
    processing: boolean;
    setProcessing: (processing: boolean) => void;
    processingAction: ProcessingAction;
    setProcessingAction: (action: ProcessingAction) => void;
    generatingVideo: boolean;

    // Voiceover state (delegated to useVoiceoverManagement)
    voiceoverProcessing: import("@/lib/api").SubtitleSource | null;
    setVoiceoverProcessing: (source: import("@/lib/api").SubtitleSource | null) => void;
    voiceoverName: string;
    setVoiceoverName: (name: string) => void;
    voiceovers: VoiceoverEntry[];
    setVoiceovers: (voiceovers: VoiceoverEntry[]) => void;
    voiceoversLoading: boolean;
    selectedVoiceoverId: string | null;
    setSelectedVoiceoverId: (id: string | null) => void;
    selectedVoiceoverSyncTimeline: import("@/lib/api").SyncTimeline | null;

    // Timeline state
    timelineEntries: TimelineEntry[];
    setTimelineEntries: (entries: TimelineEntry[]) => void;
    timelineLoading: boolean;
    setTimelineLoading: (loading: boolean) => void;

    // UI state
    currentTime: number;
    setCurrentTime: (time: number) => void;
    refreshExplanations: number;
    setRefreshExplanations: (fn: (prev: number) => number) => void;
    refreshVerification: number;
    subtitleRefreshVersion: number;

    // Ask context
    askContext: AskContextItem[];
    setAskContext: React.Dispatch<React.SetStateAction<AskContextItem[]>>;

    // Dialog state
    isSettingsOpen: boolean;
    setIsSettingsOpen: (open: boolean) => void;
    isActionsOpen: boolean;
    setIsActionsOpen: (open: boolean) => void;

    // Note generation
    generatingNote: boolean;
    setGeneratingNote: (generating: boolean) => void;

    // SSE connection
    isConnected: boolean;
    tasks: ReturnType<typeof useTaskStatus>["tasks"];
}

/**
 * Hook to manage the core state for the video page.
 * Handles content loading, SSE task monitoring, and coordinates with domain-specific hooks.
 *
 * Voiceover state is delegated to useVoiceoverManagement for better separation of concerns.
 */
export function useVideoPageState({
    videoId,
    originalLanguage,
    targetLanguage,
    learnerProfile,
    initialContent,
    initialVoiceovers,
}: UseVideoPageStateOptions): UseVideoPageStateReturn {
    // Content state - use initial data from server if available
    const [content, setContent] = useState<ContentItem | null>(initialContent ?? null);
    const [loading, setLoading] = useState(!initialContent);

    // Processing state
    const [processing, setProcessing] = useState(false);
    const [processingAction, setProcessingAction] = useState<ProcessingAction>(null);
    const generatingVideo = processing && processingAction === "video";

    // Voiceover state - delegated to specialized hook
    const voiceoverState = useVoiceoverManagement({
        videoId,
        initialVoiceovers,
    });

    // Timeline state
    const [timelineEntries, setTimelineEntries] = useState<TimelineEntry[]>([]);
    const [timelineLoading, setTimelineLoading] = useState(false);

    // UI state
    const [currentTime, setCurrentTime] = useState(0);
    const [refreshExplanations, setRefreshExplanations] = useState(0);
    const [refreshVerification, setRefreshVerification] = useState(0);
    const [subtitleRefreshVersion, setSubtitleRefreshVersion] = useState(0);

    // Ask context
    const [askContext, setAskContext] = useState<AskContextItem[]>([]);

    // Dialog state
    const [isSettingsOpen, setIsSettingsOpen] = useState(false);
    const [isActionsOpen, setIsActionsOpen] = useState(false);

    // Note generation
    const [generatingNote, setGeneratingNote] = useState(false);

    // SSE task status
    const { tasks, isConnected } = useTaskStatus(videoId);
    const { notifyTaskComplete } = useTaskNotification();
    const handledTasksRef = useRef<Set<string>>(new Set());

    // Reset handled tasks when videoId changes
    useEffect(() => {
        handledTasksRef.current = new Set();
        setSubtitleRefreshVersion(0);
    }, [videoId]);

    // Load initial content - skip if server provided initial data
    useEffect(() => {
        // Skip client fetch if server already provided initial content
        if (!videoId || initialContent) {
            // Still initialize processing state from initial content if provided
            if (initialContent) {
                const derived = deriveProcessingState(initialContent);
                setProcessing(derived.processing);
                setProcessingAction(derived.action);
                if (derived.timelineLoading) {
                    setTimelineLoading(true);
                }
            }
            return;
        }

        let cancelled = false;

        const fetchOnce = async () => {
            try {
                const contentData = await getContentMetadata(videoId);
                if (!cancelled) {
                    setContent(contentData);

                    // Initialize processing state from persisted metadata status
                    // This ensures UI shows correct state after page refresh
                    const derived = deriveProcessingState(contentData);
                    setProcessing(derived.processing);
                    setProcessingAction(derived.action);
                    if (derived.timelineLoading) {
                        setTimelineLoading(true);
                    }
                }
            } catch (error) {
                log.error("Failed to fetch content", toError(error), { videoId });
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        };

        fetchOnce();

        return () => {
            cancelled = true;
        };
    }, [videoId, initialContent]);

    // Handle SSE task updates with race condition protection
    useEffect(() => {
        let cancelled = false;

        const handleTasks = async () => {
            for (const task of Object.values(tasks)) {
                if (cancelled) return;

                const taskId = task.task_id || task.id;
                if (!taskId) continue;

                if (handledTasksRef.current.has(taskId)) continue;

                if (task.status === "ready" || task.status === "error") {
                    handledTasksRef.current.add(taskId);

                    // Only notify for live events, not initial history
                    const isLiveEvent = task._eventType !== "initial";
                    if (isLiveEvent) {
                        notifyTaskComplete(task.type, task.status, task.error);
                    }

                    // OCP: Use configuration set instead of inline array
                    if (CONTENT_REFRESH_TASK_TYPES.has(task.type)) {
                        log.info(`Task ${task.type} completed, refreshing content`, { taskType: task.type, videoId });

                        // Bump subtitle refresh version BEFORE metadata fetch
                        // This ensures UI refresh even if getContentMetadata() fails
                        if (isLiveEvent && task.status === "ready" && SUBTITLE_REFRESH_TASK_TYPES.has(task.type)) {
                            setSubtitleRefreshVersion((v) => v + 1);

                            // Optimistic update to prevent stale metadata from blocking UI
                            setContent((prev) => {
                                if (!prev) return prev;
                                const updates: Partial<ContentItem> = {};

                                if (task.type === "subtitle_generation") {
                                    updates.subtitleStatus = "ready";
                                } else if (task.type === "subtitle_enhancement") {
                                    updates.enhancedStatus = "ready";
                                } else if (task.type === "subtitle_translation") {
                                    updates.translationStatus = "ready";
                                }

                                return { ...prev, ...updates };
                            });
                        }

                        try {
                            const newContent = await getContentMetadata(videoId);
                            if (!cancelled) {
                                log.debug("Content refreshed", { videoId, videoStatus: newContent.videoStatus });

                                // For subtitle tasks, preserve optimistic status to prevent race condition
                                // where API returns stale data before DB commit is visible
                                if (SUBTITLE_REFRESH_TASK_TYPES.has(task.type)) {
                                    setContent((prev) => {
                                        if (!prev) return newContent;

                                        // Preserve the optimistic "ready" status we just set
                                        const preserved: Partial<ContentItem> = {};
                                        if (task.type === "subtitle_generation" && prev.subtitleStatus === "ready") {
                                            preserved.subtitleStatus = "ready";
                                        } else if (task.type === "subtitle_enhancement" && prev.enhancedStatus === "ready") {
                                            preserved.enhancedStatus = "ready";
                                        } else if (task.type === "subtitle_translation" && prev.translationStatus === "ready") {
                                            preserved.translationStatus = "ready";
                                        }

                                        return { ...newContent, ...preserved };
                                    });
                                } else {
                                    setContent(newContent);
                                }
                            }
                        } catch (error) {
                            log.error("Failed to refresh content after task completion", toError(error), { videoId, taskType: task.type });
                        }
                    }

                    if (cancelled) return;

                    // OCP: Check if task type matches current processing action using config map
                    const matchingAction = TASK_TO_ACTION_MAP[task.type];
                    const actionMatches = matchingAction && (
                        Array.isArray(matchingAction)
                            ? matchingAction.includes(processingAction)
                            : matchingAction === processingAction
                    );

                    if (actionMatches) {
                        setProcessing(false);
                        setProcessingAction(null);

                        // Task-specific side effects
                        if (task.type === "timeline_generation") {
                            setTimelineLoading(false);
                            try {
                                // Fetch the generated timeline (cache is keyed by output language)
                                const data = await getTimeline(videoId, {
                                    language: targetLanguage,
                                });
                                if (!cancelled) {
                                    setTimelineEntries(data.entries || []);
                                }
                            } catch (error) {
                                log.error("Failed to load timeline after generation", toError(error), { videoId });
                            }
                        }
                    } else if (task.type === "voiceover_generation") {
                        // Voiceover state is managed by useVoiceoverManagement
                        voiceoverState.setVoiceoverProcessing(null);
                        voiceoverState.setVoiceoversLoading(true);
                        try {
                            const data = await listVoiceovers(videoId);
                            if (!cancelled) {
                                voiceoverState.setVoiceovers(data.voiceovers);
                            }
                        } catch (error) {
                            log.error("Failed to refresh voiceovers after SSE", toError(error), { videoId });
                        } finally {
                            if (!cancelled) {
                                voiceoverState.setVoiceoversLoading(false);
                            }
                        }
                    } else if (task.type === "slide_explanation") {
                        setRefreshExplanations((prev) => prev + 1);
                    } else if (task.type === "fact_verification") {
                        log.info("SSE: fact_verification completed, bumping refreshVerification", { taskId, taskType: task.type, status: task.status });
                        setRefreshVerification((prev) => prev + 1);
                    } else if (task.type === "note_generation") {
                        // Note generation completed via SSE - stop the generating state
                        if (!cancelled) {
                            setGeneratingNote(false);
                        }
                    }
                }
            }
        };

        handleTasks();

        return () => {
            cancelled = true;
        };
    }, [tasks, videoId, processingAction, targetLanguage, learnerProfile, notifyTaskComplete, voiceoverState]);

    // Fallback polling when SSE not connected
    useEffect(() => {
        if (isConnected || !processing || !processingAction) return;

        const interval = setInterval(async () => {
            try {
                const data = await getContentMetadata(videoId);
                setContent(data);

                // OCP: Use configuration mapping instead of hard-coded if/else
                // Check all status fields mapped to this action (e.g., translate checks both translationStatus and enhancedStatus)
                const statusFields = ACTION_TO_STATUS_FIELDS[processingAction];
                const isComplete = statusFields?.some((field) => {
                    const status = data[field];
                    return status === "ready" || status === "error";
                });

                if (isComplete) {
                    setProcessing(false);
                    setProcessingAction(null);

                    // Task-specific cleanup
                    if (processingAction === "timeline") {
                        setTimelineLoading(false);
                    }
                }
            } catch {
                log.warn("Fallback polling failed", { videoId, action: processingAction });
            }
        }, 5000);

        return () => clearInterval(interval);
    }, [isConnected, processing, processingAction, videoId]);

    // Fallback polling for voiceover when SSE not connected
    useEffect(() => {
        if (isConnected || !voiceoverState.voiceoverProcessing) return;

        const interval = setInterval(async () => {
            try {
                voiceoverState.setVoiceoversLoading(true);
                const data = await listVoiceovers(videoId);
                voiceoverState.setVoiceovers(data.voiceovers);

                const hasProcessing = (data.voiceovers || []).some((v) => v.status === "processing");
                if (!hasProcessing) {
                    voiceoverState.setVoiceoverProcessing(null);
                }
            } catch {
                log.warn("Voiceover polling failed", { videoId });
            } finally {
                voiceoverState.setVoiceoversLoading(false);
            }
        }, 5000);

        return () => clearInterval(interval);
    }, [isConnected, voiceoverState, videoId]);

    // Load timeline when timelineStatus becomes ready
    // IMPORTANT: Do NOT trigger generation on page load.
    // This uses a read-only endpoint that returns 404 if not cached.
    const hasTimeline = content?.timelineStatus === "ready";

    useEffect(() => {
        if (content?.subtitleStatus !== "ready" || !hasTimeline) return;

        let cancelled = false;

        const loadExistingTimeline = async () => {
            try {
                setTimelineLoading(true);
                // Cache is keyed by output language (targetLanguage)
                const data = await getTimeline(videoId, {
                    language: targetLanguage,
                });
                if (!cancelled) {
                    setTimelineEntries(data.entries || []);
                }
            } catch (error) {
                // 404 is expected when no cached timeline exists.
                // Keep it silent to avoid noisy logs on first-time users.
                // APIError has status directly on object, not in response.status
                const is404 = isAPIError(error) && error.status === 404;
                if (!is404) {
                    log.error(
                        "Failed to load existing timeline",
                        toError(error),
                        { videoId }
                    );
                }
            } finally {
                if (!cancelled) {
                    setTimelineLoading(false);
                }
            }
        };

        loadExistingTimeline();

        return () => {
            cancelled = true;
        };
    }, [videoId, hasTimeline, content?.subtitleStatus, learnerProfile, targetLanguage]);

    return {
        // Content state
        content,
        setContent,
        loading,

        // Processing state
        processing,
        setProcessing,
        processingAction,
        setProcessingAction,
        generatingVideo,

        // Voiceover state (from useVoiceoverManagement)
        voiceoverProcessing: voiceoverState.voiceoverProcessing,
        setVoiceoverProcessing: voiceoverState.setVoiceoverProcessing,
        voiceoverName: voiceoverState.voiceoverName,
        setVoiceoverName: voiceoverState.setVoiceoverName,
        voiceovers: voiceoverState.voiceovers,
        setVoiceovers: voiceoverState.setVoiceovers,
        voiceoversLoading: voiceoverState.voiceoversLoading,
        selectedVoiceoverId: voiceoverState.selectedVoiceoverId,
        setSelectedVoiceoverId: voiceoverState.setSelectedVoiceoverId,
        selectedVoiceoverSyncTimeline: voiceoverState.selectedVoiceoverSyncTimeline,

        // Timeline state
        timelineEntries,
        setTimelineEntries,
        timelineLoading,
        setTimelineLoading,

        // UI state
        currentTime,
        setCurrentTime,
        refreshExplanations,
        setRefreshExplanations,
        refreshVerification,
        subtitleRefreshVersion,

        // Ask context
        askContext,
        setAskContext,

        // Dialog state
        isSettingsOpen,
        setIsSettingsOpen,
        isActionsOpen,
        setIsActionsOpen,

        // Note generation
        generatingNote,
        setGeneratingNote,

        // SSE connection
        isConnected,
        tasks,
    };
}

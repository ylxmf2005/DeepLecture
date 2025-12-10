"use client";

import { useState, useEffect, useRef } from "react";
import {
    ContentItem,
    getContentMetadata,
    listVoiceovers,
    generateTimeline,
    TimelineEntry,
    VoiceoverEntry,
} from "@/lib/api";
import { useTaskStatus } from "@/hooks/useTaskStatus";
import { useTaskNotification } from "@/hooks/useTaskNotification";
import type { TabId } from "@/stores/tabLayoutStore";
import type { AskContextItem } from "@/lib/askTypes";

export type ProcessingAction = "generate" | "enhance" | "translate" | "video" | "timeline" | null;

export interface UseVideoPageStateOptions {
    videoId: string;
    aiLanguage: string;
    learnerProfile: string;
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

    // Voiceover state
    voiceoverProcessing: import("@/lib/api").SubtitleSource | null;
    setVoiceoverProcessing: (source: import("@/lib/api").SubtitleSource | null) => void;
    voiceoverName: string;
    setVoiceoverName: (name: string) => void;
    voiceovers: VoiceoverEntry[];
    setVoiceovers: (voiceovers: VoiceoverEntry[]) => void;
    voiceoversLoading: boolean;
    selectedVoiceoverId: string | null;
    setSelectedVoiceoverId: (id: string | null) => void;

    // Timeline state
    timelineEntries: TimelineEntry[];
    setTimelineEntries: (entries: TimelineEntry[]) => void;
    timelineLoading: boolean;
    setTimelineLoading: (loading: boolean) => void;

    // UI state
    activeTab: TabId;
    setActiveTab: (tab: TabId) => void;
    currentTime: number;
    setCurrentTime: (time: number) => void;
    refreshExplanations: number;
    setRefreshExplanations: (fn: (prev: number) => number) => void;

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
 * Handles content loading, SSE task monitoring, and voiceover management.
 */
export function useVideoPageState({
    videoId,
    aiLanguage,
    learnerProfile,
}: UseVideoPageStateOptions): UseVideoPageStateReturn {
    // Content state
    const [content, setContent] = useState<ContentItem | null>(null);
    const [loading, setLoading] = useState(true);

    // Processing state
    const [processing, setProcessing] = useState(false);
    const [processingAction, setProcessingAction] = useState<ProcessingAction>(null);
    const generatingVideo = processing && processingAction === "video";

    // Voiceover state
    const [voiceoverProcessing, setVoiceoverProcessing] = useState<import("@/lib/api").SubtitleSource | null>(null);
    const [voiceoverName, setVoiceoverName] = useState("");
    const [voiceovers, setVoiceovers] = useState<VoiceoverEntry[]>([]);
    const [voiceoversLoading, setVoiceoversLoading] = useState(false);
    const [selectedVoiceoverId, setSelectedVoiceoverId] = useState<string | null>(null);

    // Timeline state
    const [timelineEntries, setTimelineEntries] = useState<TimelineEntry[]>([]);
    const [timelineLoading, setTimelineLoading] = useState(false);

    // UI state
    const [activeTab, setActiveTab] = useState<TabId>("subtitles");
    const [currentTime, setCurrentTime] = useState(0);
    const [refreshExplanations, setRefreshExplanations] = useState(0);

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
    }, [videoId]);

    // Load initial content
    useEffect(() => {
        if (!videoId) return;

        let cancelled = false;

        const fetchOnce = async () => {
            try {
                const contentData = await getContentMetadata(videoId);
                if (!cancelled) {
                    setContent(contentData);

                    // Initialize processing state from persisted metadata status
                    // This ensures UI shows correct state after page refresh
                    if (contentData.subtitleStatus === "processing") {
                        setProcessing(true);
                        setProcessingAction("generate");
                    } else if (contentData.translationStatus === "processing" || contentData.enhancedStatus === "processing") {
                        setProcessing(true);
                        setProcessingAction("translate");
                    } else if (contentData.videoStatus === "processing") {
                        setProcessing(true);
                        setProcessingAction("video");
                    } else if (contentData.timelineStatus === "processing") {
                        setProcessing(true);
                        setProcessingAction("timeline");
                        setTimelineLoading(true);
                    }
                }
            } catch (error) {
                console.error("Failed to fetch content:", error);
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
    }, [videoId]);

    // Load voiceovers
    useEffect(() => {
        const fetchVoiceovers = async () => {
            try {
                setVoiceoversLoading(true);
                const data = await listVoiceovers(videoId);
                setVoiceovers(data.voiceovers);

                if (
                    selectedVoiceoverId &&
                    !data.voiceovers.some((v: VoiceoverEntry) => v.id === selectedVoiceoverId)
                ) {
                    setSelectedVoiceoverId(null);
                }
            } catch (error) {
                console.error("Failed to load voiceovers:", error);
            } finally {
                setVoiceoversLoading(false);
            }
        };

        if (videoId) {
            fetchVoiceovers();
        }
    }, [videoId, voiceoverProcessing, selectedVoiceoverId]);

    // Handle SSE task updates
    useEffect(() => {
        Object.values(tasks).forEach((task) => {
            const taskId = task.task_id || task.id;
            if (!taskId) return;

            if (handledTasksRef.current.has(taskId)) return;

            if (task.status === "ready" || task.status === "error") {
                handledTasksRef.current.add(taskId);

                // Only notify for live events, not initial history
                const isLiveEvent = task._eventType !== "initial";
                if (isLiveEvent) {
                    notifyTaskComplete(task.type, task.status, task.error);
                }

                const shouldRefreshContent = [
                    "subtitle_generation",
                    "subtitle_enhancement",
                    "subtitle_translation",
                    "timeline_generation",
                    "video_generation",
                    "video_merge",
                    "video_import_url",
                    "pdf_merge",
                ].includes(task.type);

                if (shouldRefreshContent) {
                    console.log(`[SSE] Task ${task.type} completed, refreshing content...`);
                    getContentMetadata(videoId).then((newContent) => {
                        console.log(`[SSE] Content refreshed, videoStatus: ${newContent.videoStatus}`);
                        setContent(newContent);
                    });
                }

                if (task.type === "subtitle_generation" && processingAction === "generate") {
                    setProcessing(false);
                    setProcessingAction(null);
                } else if (task.type === "timeline_generation" && processingAction === "timeline") {
                    setProcessing(false);
                    setProcessingAction(null);
                    setTimelineLoading(false);
                    generateTimeline(videoId, aiLanguage, false, learnerProfile || undefined).then(
                        (data) => setTimelineEntries(data.timeline || [])
                    );
                } else if (task.type === "video_generation" && processingAction === "video") {
                    setProcessing(false);
                    setProcessingAction(null);
                } else if (
                    (task.type === "subtitle_enhancement" || task.type === "subtitle_translation") &&
                    processingAction === "translate"
                ) {
                    setProcessing(false);
                    setProcessingAction(null);
                } else if (task.type === "voiceover_generation") {
                    // Refresh voiceover list and release UI lock
                    setVoiceoverProcessing(null);
                    setVoiceoversLoading(true);
                    listVoiceovers(videoId)
                        .then((data) => setVoiceovers(data.voiceovers))
                        .catch((error) => console.error("Failed to refresh voiceovers after SSE:", error))
                        .finally(() => setVoiceoversLoading(false));
                } else if (task.type === "slide_explanation") {
                    setRefreshExplanations((prev) => prev + 1);
                }
            }
        });
    }, [tasks, videoId, processingAction, aiLanguage, learnerProfile, notifyTaskComplete]);

    // Fallback polling when SSE not connected
    useEffect(() => {
        if (isConnected || !processing || !processingAction) return;

        const interval = setInterval(async () => {
            try {
                const data = await getContentMetadata(videoId);
                setContent(data);

                // Check for completion or error using new feature-based status model
                if (processingAction === "generate") {
                    if (data.subtitleStatus === "ready" || data.subtitleStatus === "error") {
                        setProcessing(false);
                        setProcessingAction(null);
                    }
                } else if (processingAction === "translate") {
                    if (data.translationStatus === "ready" || data.translationStatus === "error") {
                        setProcessing(false);
                        setProcessingAction(null);
                    }
                } else if (processingAction === "timeline") {
                    if (data.timelineStatus === "ready" || data.timelineStatus === "error") {
                        setProcessing(false);
                        setProcessingAction(null);
                        setTimelineLoading(false);
                    }
                } else if (processingAction === "video") {
                    if (data.videoStatus === "ready" || data.videoStatus === "error") {
                        setProcessing(false);
                        setProcessingAction(null);
                    }
                }
            } catch (e) {
                console.error("Fallback polling failed", e);
            }
        }, 5000);

        return () => clearInterval(interval);
    }, [isConnected, processing, processingAction, videoId]);

    // Fallback polling for voiceover when SSE not connected
    useEffect(() => {
        if (isConnected || !voiceoverProcessing) return;

        const interval = setInterval(async () => {
            try {
                setVoiceoversLoading(true);
                const data = await listVoiceovers(videoId);
                setVoiceovers(data.voiceovers);

                const hasProcessing = (data.voiceovers || []).some((v) => v.status === "processing");
                if (!hasProcessing) {
                    setVoiceoverProcessing(null);
                }
            } catch (error) {
                console.error("Voiceover polling failed", error);
            } finally {
                setVoiceoversLoading(false);
            }
        }, 5000);

        return () => clearInterval(interval);
    }, [isConnected, voiceoverProcessing, videoId]);

    // Load timeline when timelineStatus becomes ready
    const hasTimeline = content?.timelineStatus === "ready";

    useEffect(() => {
        if (content?.subtitleStatus !== "ready" || !hasTimeline) {
            return;
        }

        let cancelled = false;

        const loadExistingTimeline = async () => {
            try {
                setTimelineLoading(true);
                const data = await generateTimeline(
                    videoId,
                    aiLanguage,
                    false,
                    learnerProfile || undefined
                );
                if (!cancelled) {
                    setTimelineEntries(data.timeline || []);
                }
            } catch (error) {
                console.error("Failed to load existing timeline:", error);
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
    }, [videoId, hasTimeline, content?.subtitleStatus, learnerProfile, aiLanguage]);

    return {
        content,
        setContent,
        loading,
        processing,
        setProcessing,
        processingAction,
        setProcessingAction,
        generatingVideo,
        voiceoverProcessing,
        setVoiceoverProcessing,
        voiceoverName,
        setVoiceoverName,
        voiceovers,
        setVoiceovers,
        voiceoversLoading,
        selectedVoiceoverId,
        setSelectedVoiceoverId,
        timelineEntries,
        setTimelineEntries,
        timelineLoading,
        setTimelineLoading,
        activeTab,
        setActiveTab,
        currentTime,
        setCurrentTime,
        refreshExplanations,
        setRefreshExplanations,
        askContext,
        setAskContext,
        isSettingsOpen,
        setIsSettingsOpen,
        isActionsOpen,
        setIsActionsOpen,
        generatingNote,
        setGeneratingNote,
        isConnected,
        tasks,
    };
}

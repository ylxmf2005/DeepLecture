"use client";

import { useCallback } from "react";
import { explainSlide, generateSlideLecture, uploadContent } from "@/lib/api";
import { useTaskNotification } from "@/hooks/useTaskNotification";
import type { ProcessingAction } from "../useVideoPageState";
import { useTabLayoutStore, findTabPanel, type TabId } from "@/stores/tabLayoutStore";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";
import { isUnresolvedAutoSourceLanguage } from "@/lib/sourceLanguage";

const log = logger.scope("SlideHandlers");

export interface UseSlideHandlersOptions {
    videoId: string;
    sourceLanguage: string;
    detectedSourceLanguage?: string | null;
    targetLanguage: string;
    ttsLanguage?: "source" | "target";
    learnerProfile: string;
    subtitleContextWindowSeconds: number;
    setProcessing: (processing: boolean) => void;
    setProcessingAction: (action: ProcessingAction) => void;
    setRefreshExplanations: (fn: (prev: number) => number) => void;
    setDeckStore: (videoId: string, deck: { id: string; name: string }) => void;
}

export interface UseSlideHandlersReturn {
    handleCapture: (timestamp: number, imagePath: string) => Promise<void>;
    handleGenerateSlideLecture: (force?: boolean) => Promise<void>;
    handleUploadSlide: (file: File) => Promise<void>;
}

/**
 * Handles slide capture, lecture generation, and deck upload.
 */
export function useSlideHandlers({
    videoId,
    sourceLanguage,
    detectedSourceLanguage,
    targetLanguage,
    ttsLanguage,
    learnerProfile,
    subtitleContextWindowSeconds,
    setProcessing,
    setProcessingAction,
    setRefreshExplanations,
    setDeckStore,
}: UseSlideHandlersOptions): UseSlideHandlersReturn {
    const { notifyTaskComplete, notifyOperation } = useTaskNotification();

    const activateTab = useCallback((tabId: TabId) => {
        const { panels, setActiveTab } = useTabLayoutStore.getState();
        const panel = findTabPanel(panels, tabId);
        if (panel) setActiveTab(panel, tabId);
    }, []);

    const handleCapture = useCallback(
        async (timestamp: number, imagePath: string) => {
            if (isUnresolvedAutoSourceLanguage(sourceLanguage, detectedSourceLanguage)) {
                notifyOperation(
                    "slide_explain",
                    "error",
                    "Source language is set to Auto. Generate subtitles first or choose a specific source language before creating explanations."
                );
                return;
            }
            try {
                // Submit explanation task first (saves pending entry on backend)
                await explainSlide({
                    contentId: videoId,
                    imageUrl: imagePath,
                    timestamp,
                    subtitleLanguage: sourceLanguage,
                    outputLanguage: targetLanguage,
                    learnerProfile: learnerProfile || undefined,
                    subtitleContextWindowSeconds,
                });
                // Now activate tab - component will mount and fetch history including the pending entry
                activateTab("explanations");
                // Also trigger refresh in case the tab was already active and component already mounted
                setRefreshExplanations((prev) => prev + 1);
            } catch (error) {
                log.error("Failed to start explanation generation", toError(error), { videoId, imagePath, timestamp });
                notifyOperation("slide_explain", "error", toError(error).message);
            }
        },
        [
            videoId,
            sourceLanguage,
            detectedSourceLanguage,
            targetLanguage,
            learnerProfile,
            subtitleContextWindowSeconds,
            activateTab,
            setRefreshExplanations,
            notifyOperation,
        ]
    );

    const handleGenerateSlideLecture = useCallback(
        async (force: boolean = false) => {
            if (isUnresolvedAutoSourceLanguage(sourceLanguage, detectedSourceLanguage)) {
                notifyOperation(
                    "video_generation",
                    "error",
                    "Slide video generation needs a concrete source language. Choose a specific language before starting."
                );
                return;
            }
            try {
                setProcessing(true);
                setProcessingAction("video");
                const result = await generateSlideLecture(videoId, {
                    sourceLanguage,
                    targetLanguage,
                    ttsLanguage,
                    force,
                });
                if (result.status === "ready") {
                    setProcessing(false);
                    setProcessingAction(null);

                    if (!result.taskId) {
                        notifyTaskComplete("video_generation", "ready");
                    }
                }
            } catch (err) {
                log.error("Failed to generate slide lecture", toError(err), { videoId });
                notifyTaskComplete("video_generation", "error", toError(err).message);
                setProcessing(false);
                setProcessingAction(null);
            }
        },
        [
            videoId,
            sourceLanguage,
            detectedSourceLanguage,
            targetLanguage,
            ttsLanguage,
            setProcessing,
            setProcessingAction,
            notifyOperation,
            notifyTaskComplete,
        ]
    );

    const handleUploadSlide = useCallback(
        async (file: File) => {
            if (!videoId) return;
            try {
                const res = await uploadContent(file);
                if (res.contentType === "slide") {
                    setDeckStore(videoId, { id: res.contentId, name: res.filename });
                }
            } catch (error) {
                log.error("Failed to upload slide deck", toError(error), { videoId });
                notifyOperation("slide_upload", "error", toError(error).message);
            }
        },
        [videoId, setDeckStore, notifyOperation]
    );

    return { handleCapture, handleGenerateSlideLecture, handleUploadSlide };
}

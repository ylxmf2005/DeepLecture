"use client";

import { useCallback } from "react";
import { explainSlide, generateSlideLecture, uploadContent } from "@/lib/api";
import type { ProcessingAction } from "../useVideoPageState";
import { useTabLayoutStore, findTabPanel, type TabId } from "@/stores/tabLayoutStore";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";

const log = logger.scope("SlideHandlers");

export interface UseSlideHandlersOptions {
    videoId: string;
    sourceLanguage: string;
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
    targetLanguage,
    ttsLanguage,
    learnerProfile,
    subtitleContextWindowSeconds,
    setProcessing,
    setProcessingAction,
    setRefreshExplanations,
    setDeckStore,
}: UseSlideHandlersOptions): UseSlideHandlersReturn {
    const activateTab = useCallback((tabId: TabId) => {
        const { panels, setActiveTab } = useTabLayoutStore.getState();
        const panel = findTabPanel(panels, tabId);
        if (panel) setActiveTab(panel, tabId);
    }, []);

    const handleCapture = useCallback(
        async (timestamp: number, imagePath: string) => {
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
            }
        },
        [videoId, sourceLanguage, targetLanguage, learnerProfile, subtitleContextWindowSeconds, activateTab, setRefreshExplanations]
    );

    const handleGenerateSlideLecture = useCallback(
        async (force: boolean = false) => {
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
                }
            } catch (err) {
                log.error("Failed to generate slide lecture", toError(err), { videoId });
                setProcessing(false);
                setProcessingAction(null);
            }
        },
        [videoId, sourceLanguage, targetLanguage, ttsLanguage, setProcessing, setProcessingAction]
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
            }
        },
        [videoId, setDeckStore]
    );

    return { handleCapture, handleGenerateSlideLecture, handleUploadSlide };
}

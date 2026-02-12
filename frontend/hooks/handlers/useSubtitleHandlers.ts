"use client";

import { useCallback } from "react";
import { generateSubtitles, enhanceAndTranslate } from "@/lib/api";
import { useTaskNotification } from "@/hooks/useTaskNotification";
import type { ProcessingAction } from "../useVideoPageState";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";

const log = logger.scope("SubtitleHandlers");

export interface UseSubtitleHandlersOptions {
    videoId: string;
    originalLanguage: string;
    translatedLanguage: string;
    hasSubtitles: boolean;
    hasEnhancedSubtitles: boolean;
    setProcessing: (processing: boolean) => void;
    setProcessingAction: (action: ProcessingAction) => void;
}

export interface UseSubtitleHandlersReturn {
    handleGenerateSubtitles: () => Promise<void>;
    handleTranslateSubtitles: () => Promise<void>;
}

/**
 * Handles subtitle generation and translation operations.
 */
export function useSubtitleHandlers({
    videoId,
    originalLanguage,
    translatedLanguage,
    hasSubtitles,
    hasEnhancedSubtitles,
    setProcessing,
    setProcessingAction,
}: UseSubtitleHandlersOptions): UseSubtitleHandlersReturn {
    const { notifyTaskComplete } = useTaskNotification();

    const handleGenerateSubtitles = useCallback(async () => {
        try {
            setProcessing(true);
            setProcessingAction("generate");
            const result = await generateSubtitles(videoId, originalLanguage, true);

            if (result.status === "ready") {
                setProcessing(false);
                setProcessingAction(null);

                if (!result.taskId) {
                    notifyTaskComplete("subtitle_generation", "ready");
                }
            }
        } catch (error) {
            log.error("Failed to generate subtitles", toError(error), { videoId, originalLanguage });
            notifyTaskComplete("subtitle_generation", "error", toError(error).message);
            setProcessing(false);
            setProcessingAction(null);
        }
    }, [videoId, originalLanguage, setProcessing, setProcessingAction, notifyTaskComplete]);

    const handleTranslateSubtitles = useCallback(async () => {
        if (!hasSubtitles && !hasEnhancedSubtitles) return;
        try {
            setProcessing(true);
            setProcessingAction("translate");
            const result = await enhanceAndTranslate(videoId, originalLanguage, translatedLanguage, true);

            if (result.status === "ready") {
                setProcessing(false);
                setProcessingAction(null);

                if (!result.taskId) {
                    notifyTaskComplete("subtitle_translation", "ready");
                }
            }
        } catch (error) {
            log.error("Failed to translate subtitles", toError(error), { videoId, translatedLanguage });
            notifyTaskComplete("subtitle_translation", "error", toError(error).message);
            setProcessing(false);
            setProcessingAction(null);
        }
    }, [
        videoId,
        originalLanguage,
        translatedLanguage,
        hasSubtitles,
        hasEnhancedSubtitles,
        setProcessing,
        setProcessingAction,
        notifyTaskComplete,
    ]);

    return { handleGenerateSubtitles, handleTranslateSubtitles };
}

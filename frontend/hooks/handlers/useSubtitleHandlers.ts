"use client";

import { useCallback } from "react";
import { generateSubtitles, enhanceAndTranslate } from "@/lib/api";
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
    const handleGenerateSubtitles = useCallback(async () => {
        try {
            setProcessing(true);
            setProcessingAction("generate");
            const result = await generateSubtitles(videoId, originalLanguage, true);

            if (result.status === "ready") {
                setProcessing(false);
                setProcessingAction(null);
            }
        } catch (error) {
            log.error("Failed to generate subtitles", toError(error), { videoId, originalLanguage });
            setProcessing(false);
            setProcessingAction(null);
        }
    }, [videoId, originalLanguage, setProcessing, setProcessingAction]);

    const handleTranslateSubtitles = useCallback(async () => {
        if (!hasSubtitles && !hasEnhancedSubtitles) return;
        try {
            setProcessing(true);
            setProcessingAction("translate");
            const result = await enhanceAndTranslate(videoId, originalLanguage, translatedLanguage, true);

            if (result.status === "ready") {
                setProcessing(false);
                setProcessingAction(null);
            }
        } catch (error) {
            log.error("Failed to translate subtitles", toError(error), { videoId, translatedLanguage });
            setProcessing(false);
            setProcessingAction(null);
        }
    }, [videoId, originalLanguage, translatedLanguage, hasSubtitles, hasEnhancedSubtitles, setProcessing, setProcessingAction]);

    return { handleGenerateSubtitles, handleTranslateSubtitles };
}

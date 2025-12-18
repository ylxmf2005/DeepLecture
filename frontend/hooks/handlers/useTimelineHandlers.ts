"use client";

import { useCallback } from "react";
import { generateTimeline, getTimeline, type TimelineEntry, isAPIError } from "@/lib/api";
import type { ProcessingAction } from "../useVideoPageState";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";

const log = logger.scope("TimelineHandlers");

export interface UseTimelineHandlersOptions {
    videoId: string;
    /** Source language of the video - subtitles are loaded from this language */
    originalLanguage: string;
    /** Target language for LLM output - timeline explanations will be in this language */
    targetLanguage: string;
    learnerProfile: string;
    hasSubtitles: boolean;
    setProcessing: (processing: boolean) => void;
    setProcessingAction: (action: ProcessingAction) => void;
    setTimelineLoading: (loading: boolean) => void;
    setTimelineEntries: (entries: TimelineEntry[]) => void;
}

export interface UseTimelineHandlersReturn {
    handleGenerateTimeline: () => Promise<void>;
}

/**
 * Handles timeline generation with cache-first strategy.
 * Generation is async - SSE will notify when complete.
 */
export function useTimelineHandlers({
    videoId,
    originalLanguage,
    targetLanguage,
    learnerProfile,
    hasSubtitles,
    setProcessing,
    setProcessingAction,
    setTimelineLoading,
    setTimelineEntries,
}: UseTimelineHandlersOptions): UseTimelineHandlersReturn {
    const handleGenerateTimeline = useCallback(async () => {
        if (!hasSubtitles) return;

        try {
            setProcessing(true);
            setProcessingAction("timeline");
            setTimelineLoading(true);

            // Try cache first (cache is keyed by output language)
            try {
                const cached = await getTimeline(videoId, { language: targetLanguage });
                setTimelineEntries(cached.entries || []);
                setProcessing(false);
                setProcessingAction(null);
                setTimelineLoading(false);
                return;
            } catch (err) {
                // 404 means no cached timeline, continue to generate
                const is404 = isAPIError(err) && err.status === 404;
                if (!is404) throw err;
            }

            // Submit async generation task
            // SSE will handle completion and data loading via useVideoPageState
            await generateTimeline(videoId, {
                subtitleLanguage: originalLanguage,
                outputLanguage: targetLanguage,
                learnerProfile: learnerProfile || undefined,
                force: true,
            });
            // Keep processing=true, SSE will clear it when task completes
        } catch (error) {
            log.error("Failed to generate timeline", toError(error), { videoId, originalLanguage, targetLanguage });
            setProcessing(false);
            setProcessingAction(null);
            setTimelineLoading(false);
        }
    }, [videoId, originalLanguage, targetLanguage, learnerProfile, hasSubtitles, setProcessing, setProcessingAction, setTimelineLoading, setTimelineEntries]);

    return { handleGenerateTimeline };
}

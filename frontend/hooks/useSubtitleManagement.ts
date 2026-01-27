"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import { toast } from "sonner";
import { getSubtitles, ContentItem, isAPIError } from "@/lib/api";
import { Subtitle, mergeSubtitles } from "@/lib/srt";
import { useVideoStateStore, usePlayerSubtitleMode } from "@/stores";
import { SubtitleDisplayMode } from "@/stores/types";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";

const log = logger.scope("SubtitleManagement");

export interface SubtitleState {
    subtitlesSource: Subtitle[];
    subtitlesTarget: Subtitle[];
    subtitlesDual: Subtitle[];
    subtitlesDualReversed: Subtitle[];
    subtitlesLoading: boolean;
    subtitleMode: SubtitleDisplayMode;
    currentSubtitles: Subtitle[];
}

export interface SubtitleActions {
    setSubtitleMode: (mode: SubtitleDisplayMode) => void;
}

export interface UseSubtitleManagementReturn extends SubtitleState, SubtitleActions {}

interface UseSubtitleManagementParams {
    videoId: string;
    content: ContentItem | null;
    originalLanguage: string;
    /** Target language for all AI outputs (translations, explanations, timelines, notes) */
    targetLanguage: string;
    /** Cache invalidation token: bump to force subtitle reload even when status stays `ready` */
    subtitleRefreshVersion?: number;
}

export function useSubtitleManagement({
    videoId,
    content,
    originalLanguage,
    targetLanguage,
    subtitleRefreshVersion = 0,
}: UseSubtitleManagementParams): UseSubtitleManagementReturn {
    const [subtitlesSource, setSubtitlesSource] = useState<Subtitle[]>([]);
    const [subtitlesTarget, setSubtitlesTarget] = useState<Subtitle[]>([]);
    const [subtitlesDual, setSubtitlesDual] = useState<Subtitle[]>([]);
    const [subtitlesDualReversed, setSubtitlesDualReversed] = useState<Subtitle[]>([]);
    const [subtitlesLoading, setSubtitlesLoading] = useState(false);

    // Race condition protection: only the latest request should update state
    const loadRequestIdRef = useRef(0);

    // Get subtitle mode from store
    const storedMode = usePlayerSubtitleMode(videoId);
    const setSubtitleModePlayer = useVideoStateStore((s) => s.setSubtitleModePlayer);
    const subtitleMode = storedMode;

    // Derive subtitle-related state to avoid unnecessary re-renders
    const hasSubtitles = content?.subtitleStatus === "ready";
    const hasEnhancedSubtitles = content?.enhancedStatus === "ready";
    const hasTranslation = content?.translationStatus === "ready";

    // Create a stable key based on subtitle state - changes trigger reload
    // subtitleRefreshVersion acts as cache invalidation token for SSE-triggered regeneration
    const subtitleStateKey = `${videoId}:${originalLanguage}:${targetLanguage}:${hasSubtitles}:${hasEnhancedSubtitles}:${hasTranslation}:${subtitleRefreshVersion}`;

    // Load subtitles when subtitle state changes
    // Using subtitleStateKey instead of content to prevent unnecessary reloads
    useEffect(() => {
        // Increment request ID to invalidate any in-flight requests
        const requestId = ++loadRequestIdRef.current;

        // Reset subtitle state when the subtitle state changes
        setSubtitlesSource([]);
        setSubtitlesTarget([]);
        setSubtitlesDual([]);
        setSubtitlesDualReversed([]);
        setSubtitlesLoading(false);

        // Ensure there is at least one kind of subtitles available
        if (!hasSubtitles && !hasEnhancedSubtitles) {
            return;
        }

        const loadSubtitles = async () => {
            try {
                setSubtitlesLoading(true);

                const sourceLang = hasEnhancedSubtitles
                    ? `${originalLanguage}_enhanced`
                    : originalLanguage;

                // Load source subtitles (JSON segments)
                const sourceData = await getSubtitles(videoId, sourceLang);

                // Guard: abort if a newer request has started
                if (requestId !== loadRequestIdRef.current) return;

                const sourceSubs: Subtitle[] = (sourceData.segments || []).map((seg, index) => ({
                    id: String(index + 1),
                    startTime: seg.start,
                    endTime: seg.end,
                    text: seg.text,
                }));
                setSubtitlesSource(sourceSubs);

                // Check if translated subtitles exist
                if (!hasTranslation) {
                    return;
                }

                // Load translated subtitles and build bilingual arrays
                const targetData = await getSubtitles(videoId, targetLanguage);

                // Guard: abort if a newer request has started
                if (requestId !== loadRequestIdRef.current) return;

                const targetSubs: Subtitle[] = (targetData.segments || []).map((seg, index) => ({
                    id: String(index + 1),
                    startTime: seg.start,
                    endTime: seg.end,
                    text: seg.text,
                }));
                setSubtitlesTarget(targetSubs);

                // Merge for dual modes: source-first and target-first
                const dualSubs = mergeSubtitles(sourceSubs, targetSubs, true);
                const dualReversedSubs = mergeSubtitles(sourceSubs, targetSubs, false);
                setSubtitlesDual(dualSubs);
                setSubtitlesDualReversed(dualReversedSubs);
            } catch (e) {
                // Guard: abort if a newer request has started
                if (requestId !== loadRequestIdRef.current) return;

                // 404 means subtitle doesn't exist for this language - expected state, not an error
                if (isAPIError(e) && e.code === "NOT_FOUND") {
                    log.debug("Subtitle not available for requested language", { videoId });
                    return;
                }

                const error = toError(e);
                log.error("Failed to load subtitles", error, { videoId });
                toast.error("Failed to load subtitles", {
                    description: error.message || "Please try again later",
                });
            } finally {
                // Only update loading state if this is still the current request
                if (requestId === loadRequestIdRef.current) {
                    setSubtitlesLoading(false);
                }
            }
        };

        loadSubtitles();

        // Cleanup: invalidate this request to prevent stale state writes
        return () => {
            loadRequestIdRef.current += 1;
        };
    // Dependencies are intentionally derived through subtitleStateKey which combines:
    // videoId, hasSubtitles, hasEnhancedSubtitles, hasTranslation, subtitleRefreshVersion
    // This prevents unnecessary API calls when only unrelated content fields change
    }, [subtitleStateKey, videoId, originalLanguage, targetLanguage, hasSubtitles, hasEnhancedSubtitles, hasTranslation]);

    const setSubtitleMode = (mode: SubtitleDisplayMode) => {
        if (!videoId) return;
        setSubtitleModePlayer(videoId, mode);
    };

    // Compute current subtitles based on semantic mode
    const currentSubtitles = useMemo(() => {
        if (subtitleMode === "dual" && subtitlesDual.length > 0) {
            return subtitlesDual;
        }
        if (subtitleMode === "dual_reversed" && subtitlesDualReversed.length > 0) {
            return subtitlesDualReversed;
        }
        if (subtitleMode === "target" && subtitlesTarget.length > 0) {
            return subtitlesTarget;
        }
        // Default / fallback: source only
        return subtitlesSource;
    }, [subtitleMode, subtitlesSource, subtitlesTarget, subtitlesDual, subtitlesDualReversed]);

    return {
        // State
        subtitlesSource,
        subtitlesTarget,
        subtitlesDual,
        subtitlesDualReversed,
        subtitlesLoading,
        subtitleMode,
        currentSubtitles,
        // Actions
        setSubtitleMode,
    };
}

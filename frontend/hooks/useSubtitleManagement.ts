"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { getContentSubtitles, ContentItem, API_BASE_URL } from "@/lib/api";
import { Subtitle, parseSRT, mergeSubtitles, stringifyVTT } from "@/lib/srt";
import { useVideoStateStore, usePlayerSubtitleMode } from "@/stores";

export type SubtitleMode = "en" | "zh" | "en_zh" | "zh_en";

export interface PlayerTrack {
    src: string;
    label: string;
    language: string;
}

export interface SubtitleState {
    subtitlesEn: Subtitle[];
    subtitlesZh: Subtitle[];
    subtitlesEnZh: Subtitle[];
    subtitlesZhEn: Subtitle[];
    subtitlesLoading: boolean;
    playerTracks: PlayerTrack[];
    subtitleMode: SubtitleMode;
    currentSubtitles: Subtitle[];
}

export interface SubtitleActions {
    setSubtitleMode: (mode: SubtitleMode) => void;
}

export interface UseSubtitleManagementReturn extends SubtitleState, SubtitleActions {}

interface UseSubtitleManagementParams {
    videoId: string;
    content: ContentItem | null;
}

export function useSubtitleManagement({
    videoId,
    content,
}: UseSubtitleManagementParams): UseSubtitleManagementReturn {
    const [subtitlesEn, setSubtitlesEn] = useState<Subtitle[]>([]);
    const [subtitlesZh, setSubtitlesZh] = useState<Subtitle[]>([]);
    const [subtitlesEnZh, setSubtitlesEnZh] = useState<Subtitle[]>([]);
    const [subtitlesZhEn, setSubtitlesZhEn] = useState<Subtitle[]>([]);
    const [subtitlesLoading, setSubtitlesLoading] = useState(false);
    const [playerTracks, setPlayerTracks] = useState<PlayerTrack[]>([]);

    const createdUrlsRef = useRef<string[]>([]);

    // Get subtitle mode from store
    const storedMode = usePlayerSubtitleMode(videoId);
    const setSubtitleModePlayer = useVideoStateStore((s) => s.setSubtitleModePlayer);
    const subtitleMode = storedMode;

    // Derive subtitle-related state to avoid unnecessary re-renders
    const hasSubtitles = content?.subtitleStatus === "ready";
    const hasEnhancedSubtitles = content?.enhancedStatus === "ready";
    const hasTranslation = content?.translationStatus === "ready";

    // Create a stable key based on subtitle state - only changes when subtitle status actually changes
    const subtitleStateKey = `${videoId}:${hasSubtitles}:${hasEnhancedSubtitles}:${hasTranslation}`;

    // Load subtitles and create player tracks when subtitle state actually changes
    // Using subtitleStateKey instead of content to prevent unnecessary reloads
    useEffect(() => {
        // Reset subtitle state and cleanup blob URLs when the subtitle state changes
        createdUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
        createdUrlsRef.current = [];
        setPlayerTracks([]);

        setSubtitlesEn([]);
        setSubtitlesZh([]);
        setSubtitlesEnZh([]);
        setSubtitlesZhEn([]);

        // Ensure there is at least one kind of subtitles available
        if (!hasSubtitles && !hasEnhancedSubtitles) {
            return;
        }

        const loadSubtitlesAndTracks = async () => {
            try {
                setSubtitlesLoading(true);

                // Load original English subtitles
                const enContent = await getContentSubtitles(
                    videoId,
                    hasEnhancedSubtitles ? "enhanced" : "original",
                    "srt"
                );
                const enSubs = parseSRT(enContent);
                setSubtitlesEn(enSubs);

                const tracks: PlayerTrack[] = [];

                // Use backend API for single-language tracks
                const enTrackUrl = `${API_BASE_URL}/api/content/${videoId}/subtitles?format=vtt&lang=${
                    hasEnhancedSubtitles ? "enhanced" : "original"
                }`;
                tracks.push({
                    src: enTrackUrl,
                    label: "EN",
                    language: "en",
                });

                // Check if translated subtitles exist
                if (!hasTranslation) {
                    setPlayerTracks(tracks);
                    return;
                }

                // Load translated Chinese subtitles and build bilingual tracks
                const zhContent = await getContentSubtitles(videoId, "translated", "srt");
                const zhSubs = parseSRT(zhContent);
                setSubtitlesZh(zhSubs);

                const enZhSubs = mergeSubtitles(enSubs, zhSubs, true);
                const zhEnSubs = mergeSubtitles(enSubs, zhSubs, false);
                setSubtitlesEnZh(enZhSubs);
                setSubtitlesZhEn(zhEnSubs);

                // Use backend API for ZH track
                const zhTrackUrl = `${API_BASE_URL}/api/content/${videoId}/subtitles?format=vtt&lang=translated`;
                tracks.push({
                    src: zhTrackUrl,
                    label: "ZH",
                    language: "zh",
                });

                // Bilingual tracks must still be generated frontend-side
                const enZhBlob = new Blob([stringifyVTT(enZhSubs)], { type: "text/vtt" });
                const enZhUrl = URL.createObjectURL(enZhBlob);
                createdUrlsRef.current.push(enZhUrl);
                tracks.push({
                    src: enZhUrl,
                    label: "EN+ZH",
                    language: "en-zh",
                });

                const zhEnBlob = new Blob([stringifyVTT(zhEnSubs)], { type: "text/vtt" });
                const zhEnUrl = URL.createObjectURL(zhEnBlob);
                createdUrlsRef.current.push(zhEnUrl);
                tracks.push({
                    src: zhEnUrl,
                    label: "ZH+EN",
                    language: "zh-en",
                });

                setPlayerTracks(tracks);
            } catch (e) {
                console.error("Failed to generate subtitles for player/sidebar", e);
            } finally {
                setSubtitlesLoading(false);
            }
        };

        loadSubtitlesAndTracks();

        return () => {
            createdUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
            createdUrlsRef.current = [];
        };
    // Dependencies are intentionally derived through subtitleStateKey which combines:
    // videoId, hasSubtitles, hasEnhancedSubtitles, hasTranslation
    // This prevents unnecessary API calls when only unrelated content fields change
    }, [subtitleStateKey, videoId, hasSubtitles, hasEnhancedSubtitles, hasTranslation]);

    const setSubtitleMode = (mode: SubtitleMode) => {
        if (!videoId) return;
        setSubtitleModePlayer(videoId, mode);
    };

    // Compute current subtitles based on mode
    const currentSubtitles = useMemo(() => {
        if (subtitleMode === "en_zh" && subtitlesEnZh.length > 0) {
            return subtitlesEnZh;
        }
        if (subtitleMode === "zh_en" && subtitlesZhEn.length > 0) {
            return subtitlesZhEn;
        }
        if (subtitleMode === "zh" && subtitlesZh.length > 0) {
            return subtitlesZh;
        }
        // Default / fallback: English only
        return subtitlesEn;
    }, [subtitleMode, subtitlesEn, subtitlesZh, subtitlesEnZh, subtitlesZhEn]);

    return {
        // State
        subtitlesEn,
        subtitlesZh,
        subtitlesEnZh,
        subtitlesZhEn,
        subtitlesLoading,
        playerTracks,
        subtitleMode,
        currentSubtitles,
        // Actions
        setSubtitleMode,
    };
}

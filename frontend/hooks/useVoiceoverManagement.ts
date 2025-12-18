"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
    listVoiceovers,
    getVoiceoverSyncTimeline,
    VoiceoverEntry,
    SyncTimeline,
    SubtitleSource,
} from "@/lib/api";
import { useVideoStateStore } from "@/stores/useVideoStateStore";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";

const log = logger.scope("VoiceoverManagement");

export interface UseVoiceoverManagementOptions {
    videoId: string;
    /** Initial voiceovers from server component (eliminates client waterfall) */
    initialVoiceovers?: VoiceoverEntry[];
}

export interface UseVoiceoverManagementReturn {
    // Processing state
    voiceoverProcessing: SubtitleSource | null;
    setVoiceoverProcessing: (source: SubtitleSource | null) => void;

    // Form state
    voiceoverName: string;
    setVoiceoverName: (name: string) => void;

    // List state
    voiceovers: VoiceoverEntry[];
    setVoiceovers: (voiceovers: VoiceoverEntry[]) => void;
    voiceoversLoading: boolean;
    setVoiceoversLoading: (loading: boolean) => void;

    // Selection state
    selectedVoiceoverId: string | null;
    setSelectedVoiceoverId: (id: string | null) => void;
    selectedVoiceoverSyncTimeline: SyncTimeline | null;

    // Actions
    refreshVoiceovers: () => Promise<void>;
}

/**
 * Hook to manage voiceover state including list, selection, and sync timeline.
 * Extracted from useVideoPageState to follow Single Responsibility Principle.
 */
export function useVoiceoverManagement({
    videoId,
    initialVoiceovers,
}: UseVoiceoverManagementOptions): UseVoiceoverManagementReturn {
    // Processing state
    const [voiceoverProcessing, setVoiceoverProcessing] = useState<SubtitleSource | null>(null);

    // Form state
    const [voiceoverName, setVoiceoverName] = useState("");

    // List state - use initial data from server if available
    const [voiceovers, setVoiceovers] = useState<VoiceoverEntry[]>(initialVoiceovers ?? []);
    const [voiceoversLoading, setVoiceoversLoading] = useState(false);

    // Sync timeline state
    const [selectedVoiceoverSyncTimeline, setSelectedVoiceoverSyncTimeline] = useState<SyncTimeline | null>(null);

    // Selected voiceover ID - persisted to localStorage via zustand store
    const selectedVoiceoverId = useVideoStateStore(
        (state) => state.videos[videoId]?.selectedVoiceoverId ?? null
    );
    const setSelectedVoiceoverIdStore = useVideoStateStore((state) => state.setSelectedVoiceoverId);
    const setSelectedVoiceoverId = useCallback(
        (id: string | null) => setSelectedVoiceoverIdStore(videoId, id),
        [videoId, setSelectedVoiceoverIdStore]
    );

    // Track if this is the initial load
    const hasInitialVoiceovers = initialVoiceovers && initialVoiceovers.length > 0;
    const isInitialLoadRef = useRef(true);

    // Refresh voiceovers action
    const refreshVoiceovers = useCallback(async () => {
        try {
            setVoiceoversLoading(true);
            const data = await listVoiceovers(videoId);
            setVoiceovers(data.voiceovers);

            // Validate stored selection
            const currentSelectedId = useVideoStateStore.getState().videos[videoId]?.selectedVoiceoverId;
            if (
                currentSelectedId &&
                !data.voiceovers.some((v: VoiceoverEntry) => v.id === currentSelectedId)
            ) {
                setSelectedVoiceoverId(null);
            }
        } catch (error) {
            log.error("Failed to load voiceovers", toError(error), { videoId });
        } finally {
            setVoiceoversLoading(false);
        }
    }, [videoId, setSelectedVoiceoverId]);

    // Load voiceovers - skip initial fetch if server provided initial data
    useEffect(() => {
        if (!videoId) return;

        if (isInitialLoadRef.current && hasInitialVoiceovers) {
            isInitialLoadRef.current = false;
            // Validate initial voiceovers against stored selection
            const currentSelectedId = useVideoStateStore.getState().videos[videoId]?.selectedVoiceoverId;
            if (
                currentSelectedId &&
                !initialVoiceovers.some((v: VoiceoverEntry) => v.id === currentSelectedId)
            ) {
                setSelectedVoiceoverId(null);
            }
        } else {
            refreshVoiceovers();
        }
    }, [videoId, voiceoverProcessing, hasInitialVoiceovers, initialVoiceovers, setSelectedVoiceoverId, refreshVoiceovers]);

    // Load sync timeline when voiceover is selected
    useEffect(() => {
        if (!selectedVoiceoverId || !videoId) {
            setSelectedVoiceoverSyncTimeline(null);
            return;
        }

        let cancelled = false;

        const fetchSyncTimeline = async () => {
            try {
                const timeline = await getVoiceoverSyncTimeline(videoId, selectedVoiceoverId);
                if (!cancelled) {
                    setSelectedVoiceoverSyncTimeline(timeline);
                }
            } catch (error) {
                log.error("Failed to load voiceover sync timeline", toError(error), { videoId, voiceoverId: selectedVoiceoverId });
                if (!cancelled) {
                    setSelectedVoiceoverSyncTimeline(null);
                }
            }
        };

        fetchSyncTimeline();

        return () => {
            cancelled = true;
        };
    }, [videoId, selectedVoiceoverId]);

    return {
        voiceoverProcessing,
        setVoiceoverProcessing,
        voiceoverName,
        setVoiceoverName,
        voiceovers,
        setVoiceovers,
        voiceoversLoading,
        setVoiceoversLoading,
        selectedVoiceoverId,
        setSelectedVoiceoverId,
        selectedVoiceoverSyncTimeline,
        refreshVoiceovers,
    };
}

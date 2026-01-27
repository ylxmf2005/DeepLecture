"use client";

import { useEffect, useMemo, useState } from "react";
import type { SubtitleSource, SyncTimeline, VoiceoverEntry } from "@/lib/api";
import { getVoiceoverTimeline, listVoiceovers } from "@/lib/api";
import { useSelectedVoiceoverId, useVideoStateStore } from "@/stores";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";

const log = logger.scope("VoiceoverManagement");

export interface UseVoiceoverManagementOptions {
    videoId: string;
    initialVoiceovers?: VoiceoverEntry[];
}

export interface UseVoiceoverManagementReturn {
    // Generation UI state
    voiceoverProcessing: SubtitleSource | null;
    setVoiceoverProcessing: (source: SubtitleSource | null) => void;
    voiceoverName: string;
    setVoiceoverName: (name: string) => void;

    // List state
    voiceovers: VoiceoverEntry[];
    setVoiceovers: React.Dispatch<React.SetStateAction<VoiceoverEntry[]>>;
    voiceoversLoading: boolean;
    setVoiceoversLoading: (loading: boolean) => void;

    // Selection (persisted per video)
    selectedVoiceoverId: string | null;
    setSelectedVoiceoverId: (id: string | null) => void;
    selectedVoiceoverSyncTimeline: SyncTimeline | null;
}

export function useVoiceoverManagement({
    videoId,
    initialVoiceovers,
}: UseVoiceoverManagementOptions): UseVoiceoverManagementReturn {
    const [voiceoverProcessing, setVoiceoverProcessing] = useState<SubtitleSource | null>(null);
    const [voiceoverName, setVoiceoverName] = useState("");
    const [voiceovers, setVoiceovers] = useState<VoiceoverEntry[]>(initialVoiceovers ?? []);
    const [voiceoversLoading, setVoiceoversLoading] = useState(false);
    const [selectedVoiceoverSyncTimeline, setSelectedVoiceoverSyncTimeline] = useState<SyncTimeline | null>(null);

    const selectedVoiceoverId = useSelectedVoiceoverId(videoId);
    const setSelectedVoiceoverIdStore = useVideoStateStore((s) => s.setSelectedVoiceoverId);
    const setSelectedVoiceoverId = (id: string | null) => setSelectedVoiceoverIdStore(videoId, id);

    // Load voiceovers list once per video (server may have initialVoiceovers from SSR)
    useEffect(() => {
        let cancelled = false;

        if (!videoId) return;
        if (initialVoiceovers && initialVoiceovers.length > 0) return;

        (async () => {
            try {
                setVoiceoversLoading(true);
                const data = await listVoiceovers(videoId);
                if (!cancelled) {
                    setVoiceovers(data.voiceovers ?? []);
                }
            } catch (error) {
                log.error("Failed to load voiceovers", toError(error), { videoId });
            } finally {
                if (!cancelled) {
                    setVoiceoversLoading(false);
                }
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [initialVoiceovers, videoId]);

    const selectedVoiceover = useMemo(
        () => (selectedVoiceoverId ? voiceovers.find((v) => v.id === selectedVoiceoverId) ?? null : null),
        [selectedVoiceoverId, voiceovers]
    );

    // Load sync timeline JSON for the selected voiceover (used by VideoPlayer sync mode)
    useEffect(() => {
        let cancelled = false;

        if (!videoId || !selectedVoiceoverId) {
            setSelectedVoiceoverSyncTimeline(null);
            return;
        }

        // Avoid fetching timeline for non-ready tracks
        if (selectedVoiceover && selectedVoiceover.status && selectedVoiceover.status !== "done") {
            setSelectedVoiceoverSyncTimeline(null);
            return;
        }

        (async () => {
            try {
                const timeline = await getVoiceoverTimeline(videoId, selectedVoiceoverId);
                if (!cancelled) {
                    setSelectedVoiceoverSyncTimeline(timeline);
                }
            } catch (error) {
                if (!cancelled) {
                    setSelectedVoiceoverSyncTimeline(null);
                }
                log.warn("Failed to load voiceover sync timeline", { videoId, selectedVoiceoverId });
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [selectedVoiceover, selectedVoiceoverId, videoId]);

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
    };
}


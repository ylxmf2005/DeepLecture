"use client";

import { useCallback } from "react";
import { toast } from "sonner";
import { generateVoiceover, listVoiceovers, deleteVoiceover, updateVoiceover, type SubtitleSource, type VoiceoverEntry } from "@/lib/api";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";

const log = logger.scope("VoiceoverHandlers");

export interface UseVoiceoverHandlersOptions {
    videoId: string;
    voiceoverName: string;
    originalLanguage: string;
    translatedLanguage: string;
    selectedVoiceoverId: string | null;
    setVoiceoverProcessing: (source: SubtitleSource | null) => void;
    setVoiceovers: (voiceovers: VoiceoverEntry[]) => void;
    setSelectedVoiceoverId: (id: string | null) => void;
}

export interface UseVoiceoverHandlersReturn {
    handleGenerateVoiceover: (source: SubtitleSource) => Promise<void>;
    handleDeleteVoiceover: (voiceoverId: string) => Promise<void>;
    handleUpdateVoiceover: (voiceoverId: string, name: string) => Promise<void>;
}

/**
 * Handles voiceover generation and deletion.
 */
export function useVoiceoverHandlers({
    videoId,
    voiceoverName,
    originalLanguage,
    translatedLanguage,
    selectedVoiceoverId,
    setVoiceoverProcessing,
    setVoiceovers,
    setSelectedVoiceoverId,
}: UseVoiceoverHandlersOptions): UseVoiceoverHandlersReturn {
    const handleGenerateVoiceover = useCallback(
        async (source: SubtitleSource) => {
            const name = voiceoverName.trim();
            if (!name) {
                toast.warning("Please enter a name for this voiceover first.");
                return;
            }

            const ttsLanguage = source === "original" ? originalLanguage : translatedLanguage;

            try {
                setVoiceoverProcessing(source);
                await generateVoiceover(videoId, source, name, ttsLanguage);
                const data = await listVoiceovers(videoId);
                setVoiceovers(data.voiceovers);
            } catch (error) {
                log.error("Failed to generate voiceover", toError(error), { videoId, voiceoverName });
                setVoiceoverProcessing(null);
            }
        },
        [videoId, voiceoverName, originalLanguage, translatedLanguage, setVoiceoverProcessing, setVoiceovers]
    );

    const handleDeleteVoiceover = useCallback(
        async (voiceoverId: string) => {
            try {
                await deleteVoiceover(videoId, voiceoverId);
                const data = await listVoiceovers(videoId);
                setVoiceovers(data.voiceovers);
                if (voiceoverId === selectedVoiceoverId) {
                    setSelectedVoiceoverId(null);
                }
            } catch (error) {
                log.error("Failed to delete voiceover", toError(error), { videoId, voiceoverId });
            }
        },
        [videoId, selectedVoiceoverId, setSelectedVoiceoverId, setVoiceovers]
    );

    const handleUpdateVoiceover = useCallback(
        async (voiceoverId: string, name: string) => {
            try {
                await updateVoiceover(videoId, voiceoverId, name);
                const data = await listVoiceovers(videoId);
                setVoiceovers(data.voiceovers);
                if (voiceoverId === selectedVoiceoverId) {
                    setSelectedVoiceoverId(name);
                }
                toast.success("Voiceover renamed");
            } catch (error) {
                log.error("Failed to update voiceover", toError(error), { videoId, voiceoverId, name });
                toast.error("Failed to rename voiceover");
                throw error;
            }
        },
        [videoId, selectedVoiceoverId, setSelectedVoiceoverId, setVoiceovers]
    );

    return { handleGenerateVoiceover, handleDeleteVoiceover, handleUpdateVoiceover };
}

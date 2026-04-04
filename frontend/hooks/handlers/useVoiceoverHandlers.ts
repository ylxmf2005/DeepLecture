"use client";

import { useCallback } from "react";
import { generateVoiceover, listVoiceovers, deleteVoiceover, updateVoiceover, type SubtitleSource, type VoiceoverEntry } from "@/lib/api";
import { useTaskNotification } from "@/hooks/useTaskNotification";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";
import { isUnresolvedAutoSourceLanguage } from "@/lib/sourceLanguage";

const log = logger.scope("VoiceoverHandlers");

export interface UseVoiceoverHandlersOptions {
    videoId: string;
    voiceoverName: string;
    originalLanguage: string;
    detectedSourceLanguage?: string | null;
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
    detectedSourceLanguage,
    translatedLanguage,
    selectedVoiceoverId,
    setVoiceoverProcessing,
    setVoiceovers,
    setSelectedVoiceoverId,
}: UseVoiceoverHandlersOptions): UseVoiceoverHandlersReturn {
    const { notifyTaskComplete, notifyOperation } = useTaskNotification();

    const handleGenerateVoiceover = useCallback(
        async (source: SubtitleSource) => {
            const name = voiceoverName.trim();
            if (!name) {
                notifyOperation("voiceover_name_required", "error");
                return;
            }
            if (
                source === "original" &&
                isUnresolvedAutoSourceLanguage(originalLanguage, detectedSourceLanguage)
            ) {
                notifyTaskComplete(
                    "voiceover_generation",
                    "error",
                    "Source language is set to Auto. Generate subtitles first so the detected language can be reused for voiceover generation."
                );
                return;
            }

            const ttsLanguage = source === "original" ? originalLanguage : translatedLanguage;

            try {
                setVoiceoverProcessing(source);
                const response = await generateVoiceover(videoId, source, name, ttsLanguage);
                const data = await listVoiceovers(videoId);
                setVoiceovers(data.voiceovers);

                if (!response.taskId) {
                    notifyTaskComplete("voiceover_generation", "ready");
                    setVoiceoverProcessing(null);
                }
            } catch (error) {
                log.error("Failed to generate voiceover", toError(error), { videoId, voiceoverName });
                notifyTaskComplete("voiceover_generation", "error", toError(error).message);
                setVoiceoverProcessing(null);
            }
        },
        [
            videoId,
            voiceoverName,
            originalLanguage,
            detectedSourceLanguage,
            translatedLanguage,
            setVoiceoverProcessing,
            setVoiceovers,
            notifyOperation,
            notifyTaskComplete,
        ]
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
                notifyOperation("voiceover_delete", "error", toError(error).message);
            }
        },
        [videoId, selectedVoiceoverId, setSelectedVoiceoverId, setVoiceovers, notifyOperation]
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
                notifyOperation("voiceover_rename", "success");
            } catch (error) {
                log.error("Failed to update voiceover", toError(error), { videoId, voiceoverId, name });
                notifyOperation("voiceover_rename", "error", toError(error).message);
                throw error;
            }
        },
        [videoId, selectedVoiceoverId, setSelectedVoiceoverId, setVoiceovers, notifyOperation]
    );

    return { handleGenerateVoiceover, handleDeleteVoiceover, handleUpdateVoiceover };
}

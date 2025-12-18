/**
 * Voiceover APIs - Generate and manage voiceovers
 */

import { api } from "./client";
import { withTTSOverrides } from "./ai-overrides";
import type {
    SubtitleSource,
    VoiceoverResponse,
    ListVoiceoversResponse,
    SyncTimeline,
} from "./types";

export const generateVoiceover = async (
    contentId: string,
    subtitleSource: SubtitleSource,
    voiceoverName: string,
    language: string
): Promise<VoiceoverResponse> => {
    const subtitleSourcePayload =
        subtitleSource === "original"
            ? { type: "transcript", language }
            : { type: "translation", language };

    const response = await api.post<VoiceoverResponse>(
        `/content/${contentId}/voiceovers`,
        withTTSOverrides({
            subtitle_source: subtitleSourcePayload,
            voiceover_name: voiceoverName,
            language,
        })
    );
    return response.data;
};

export const listVoiceovers = async (contentId: string): Promise<ListVoiceoversResponse> => {
    const response = await api.get<ListVoiceoversResponse>(`/content/${contentId}/voiceovers`);
    return response.data;
};

export const deleteVoiceover = async (
    contentId: string,
    voiceoverId: string
): Promise<{ deleted: boolean }> => {
    const response = await api.delete<{ deleted: boolean }>(
        `/content/${contentId}/voiceovers/${voiceoverId}`
    );
    return response.data;
};

export const getVoiceoverSyncTimeline = async (
    contentId: string,
    voiceoverId: string
): Promise<SyncTimeline> => {
    const response = await api.get<SyncTimeline>(
        `/content/${contentId}/voiceovers/${encodeURIComponent(voiceoverId)}/timeline`
    );
    return response.data;
};

export const updateVoiceover = async (
    contentId: string,
    voiceoverId: string,
    name: string
): Promise<VoiceoverResponse> => {
    const response = await api.patch<VoiceoverResponse>(
        `/content/${contentId}/voiceovers/${encodeURIComponent(voiceoverId)}`,
        { name }
    );
    return response.data;
};

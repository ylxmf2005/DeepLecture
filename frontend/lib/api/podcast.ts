/**
 * Podcast APIs - Generate and retrieve NotebookLM-style dialogue podcasts
 */

import { api, API_BASE_URL } from "./client";
import { withLLMOverrides } from "./ai-overrides";

export interface PodcastSegment {
    speaker: "host" | "guest";
    text: string;
    startTime: number;
    endTime: number;
}

export interface PodcastResponse {
    contentId: string;
    language: string;
    title: string;
    summary: string;
    segments: PodcastSegment[];
    segmentCount: number;
    duration: number;
    updatedAt: string | null;
}

export interface GeneratePodcastResponse {
    contentId: string;
    taskId: string;
    status: "pending";
    message: string;
}

export type PodcastContextMode = "subtitle" | "slide" | "both";
export type PodcastSubjectType = "auto" | "stem" | "humanities";

export interface GeneratePodcastParams {
    contentId: string;
    language: string;
    contextMode?: PodcastContextMode;
    instruction?: string;
    subjectType?: PodcastSubjectType;
    ttsModelHost?: string;
    ttsModelGuest?: string;
    voiceIdHost?: string;
    voiceIdGuest?: string;
    turnGapSeconds?: number;
}

export const getPodcast = async (contentId: string, language: string): Promise<PodcastResponse | null> => {
    try {
        const response = await api.get<PodcastResponse>(`/podcast/${contentId}`, {
            params: { language },
        });
        return response.data;
    } catch (error: unknown) {
        if (error && typeof error === "object" && "status" in error && error.status === 404) {
            return null;
        }
        throw error;
    }
};

/**
 * Get the audio URL for a podcast (for <audio> element src).
 */
export const getPodcastAudioUrl = (contentId: string, language: string): string => {
    return `${API_BASE_URL}/api/podcast/${contentId}/audio?language=${encodeURIComponent(language)}`;
};

export const generatePodcast = async (
    params: GeneratePodcastParams
): Promise<GeneratePodcastResponse> => {
    const response = await api.post<GeneratePodcastResponse>(
        `/podcast/${params.contentId}/generate`,
        withLLMOverrides({
            language: params.language,
            context_mode: params.contextMode ?? "both",
            user_instruction: params.instruction ?? "",
            subject_type: params.subjectType ?? "auto",
            tts_model_host: params.ttsModelHost,
            tts_model_guest: params.ttsModelGuest,
            voice_id_host: params.voiceIdHost,
            voice_id_guest: params.voiceIdGuest,
            turn_gap_seconds: params.turnGapSeconds ?? 0.3,
        })
    );
    return response.data;
};

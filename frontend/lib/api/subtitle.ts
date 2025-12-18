/**
 * Subtitle APIs - Generate, translate, and fetch subtitles
 */

import { api } from "./client";
import { withLLMOverrides } from "./ai-overrides";
import type {
    SubtitleResponse,
    SubtitleGenerateResponse,
    TranslationResponse,
} from "./types";

export const generateSubtitles = async (
    contentId: string,
    language: string,
    force: boolean = false
): Promise<SubtitleGenerateResponse> => {
    const response = await api.post<SubtitleGenerateResponse>(
        `/subtitle/${contentId}/generate`,
        { language, force }
    );
    return response.data;
};

export const enhanceAndTranslate = async (
    contentId: string,
    sourceLanguage: string,
    targetLanguage: string,
    force: boolean = false
): Promise<TranslationResponse> => {
    const response = await api.post<TranslationResponse>(
        `/subtitle/${contentId}/enhance-translate`,
        withLLMOverrides({
            source_language: sourceLanguage,
            target_language: targetLanguage,
            force,
        })
    );
    return response.data;
};

export const getSubtitles = async (
    contentId: string,
    language: string
): Promise<SubtitleResponse> => {
    const response = await api.get<SubtitleResponse>(`/subtitle/${contentId}`, {
        params: { language },
    });
    return response.data;
};

export const getSubtitlesVtt = async (
    contentId: string,
    language: string
): Promise<string> => {
    const response = await api.get<string>(`/subtitle/${contentId}/vtt`, {
        params: { language },
    });
    return response.data;
};

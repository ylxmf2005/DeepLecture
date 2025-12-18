/**
 * Explanation APIs - Capture and explain slides
 */

import { api } from "./client";
import { withLLMOverrides } from "./ai-overrides";
import type { CaptureResponse, ExplanationGenerateResponse, ExplanationHistoryResponse } from "./types";

export const captureSlide = async (
    contentId: string,
    timestamp: number
): Promise<CaptureResponse> => {
    const response = await api.post<CaptureResponse>(`/content/${contentId}/screenshots`, {
        timestamp,
    });
    return response.data;
};

export interface ExplainSlideParams {
    contentId: string;
    imageUrl: string;
    timestamp: number;
    /** Source language for subtitle context (optional) */
    subtitleLanguage?: string;
    /** Target language for LLM output */
    outputLanguage: string;
    learnerProfile?: string;
    subtitleContextWindowSeconds?: number;
}

export const explainSlide = async (
    params: ExplainSlideParams
): Promise<ExplanationGenerateResponse> => {
    const {
        contentId,
        imageUrl,
        timestamp,
        subtitleLanguage,
        outputLanguage,
        learnerProfile,
        subtitleContextWindowSeconds,
    } = params;
    const response = await api.post<ExplanationGenerateResponse>(
        `/content/${contentId}/explanations`,
        withLLMOverrides({
            image_url: imageUrl,
            timestamp,
            subtitle_language: subtitleLanguage,
            output_language: outputLanguage,
            learner_profile: learnerProfile,
            subtitle_context_window_seconds: subtitleContextWindowSeconds,
        })
    );
    return response.data;
};

export const getExplanationHistory = async (
    contentId: string
): Promise<ExplanationHistoryResponse> => {
    const response = await api.get<ExplanationHistoryResponse>(`/content/${contentId}/explanations`);
    return response.data;
};

export const deleteExplanation = async (
    contentId: string,
    explanationId: string
): Promise<void> => {
    await api.delete(`/content/${contentId}/explanations/${explanationId}`);
};

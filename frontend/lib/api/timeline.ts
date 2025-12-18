/**
 * Timeline APIs - Generate and fetch video timelines
 */

import { api } from "./client";
import { withLLMOverrides } from "./ai-overrides";
import type { TimelineResponse, TimelineGenerateResponse } from "./types";

export interface GetTimelineOptions {
    language?: string;
}

export interface GenerateTimelineOptions {
    /** Source language for loading subtitles */
    subtitleLanguage: string;
    /** Target language for LLM output */
    outputLanguage: string;
    learnerProfile?: string;
    force?: boolean;
}

/**
 * Fetch existing timeline (read-only).
 * Returns 404 if no cached timeline exists.
 */
export const getTimeline = async (
    contentId: string,
    options: GetTimelineOptions = {}
): Promise<TimelineResponse> => {
    const response = await api.get<TimelineResponse>(`/timeline/${contentId}`, {
        params: options.language ? { language: options.language } : undefined,
    });
    return response.data;
};

/**
 * Generate timeline using LLM.
 */
export const generateTimeline = async (
    contentId: string,
    options: GenerateTimelineOptions
): Promise<TimelineGenerateResponse> => {
    const response = await api.post<TimelineGenerateResponse>(
        `/timeline/${contentId}/generate`,
        withLLMOverrides({
            subtitle_language: options.subtitleLanguage,
            output_language: options.outputLanguage,
            learner_profile: options.learnerProfile,
            force: options.force ?? false,
        })
    );
    return response.data;
};

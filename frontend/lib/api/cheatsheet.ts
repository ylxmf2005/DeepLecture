/**
 * Cheatsheet APIs - Get, save, and generate exam cheatsheets
 */

import { api } from "./client";
import { withLLMOverrides } from "./ai-overrides";
import type { CheatsheetResponse, GenerateCheatsheetResponse } from "./types";

export const getVideoCheatsheet = async (contentId: string): Promise<CheatsheetResponse> => {
    const response = await api.get<CheatsheetResponse>("/cheatsheet", {
        params: { contentId },
    });
    return response.data;
};

export const saveVideoCheatsheet = async (
    contentId: string,
    content: string
): Promise<CheatsheetResponse> => {
    const response = await api.post<CheatsheetResponse>("/cheatsheet", {
        content_id: contentId,
        content,
    });
    return response.data;
};

export type CheatsheetContextMode = "auto" | "subtitle" | "slide" | "both";
export type CheatsheetCriticality = "high" | "medium" | "low";
export type CheatsheetSubjectType = "auto" | "stem" | "humanities";

export interface GenerateCheatsheetParams {
    contentId: string;
    language: string;
    contextMode?: CheatsheetContextMode;
    instruction?: string;
    minCriticality?: CheatsheetCriticality;
    targetPages?: number;
    subjectType?: CheatsheetSubjectType;
}

export const generateVideoCheatsheet = async (
    params: GenerateCheatsheetParams
): Promise<GenerateCheatsheetResponse> => {
    const response = await api.post<GenerateCheatsheetResponse>(
        "/cheatsheet/generate",
        withLLMOverrides({
            content_id: params.contentId,
            language: params.language,
            context_mode: params.contextMode ?? "auto",
            user_instruction: params.instruction ?? "",
            min_criticality: params.minCriticality ?? "medium",
            target_pages: params.targetPages ?? 2,
            subject_type: params.subjectType ?? "auto",
        })
    );
    return response.data;
};

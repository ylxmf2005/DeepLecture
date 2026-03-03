/**
 * Flashcard APIs - Get and generate AI flashcards for active recall study
 */

import { api } from "./client";
import { withLLMOverrides } from "./ai-overrides";

export interface FlashcardItem {
    front: string;
    back: string;
    sourceTimestamp: number | null;
    sourceCategory: string | null;
}

export interface FlashcardResponse {
    contentId: string;
    language: string;
    items: FlashcardItem[];
    count: number;
    updatedAt: string | null;
}

export interface GenerateFlashcardResponse {
    contentId: string;
    taskId: string;
    status: "pending";
    message: string;
}

export type FlashcardContextMode = "subtitle" | "slide" | "both";
export type FlashcardCriticality = "high" | "medium" | "low";
export type FlashcardSubjectType = "auto" | "stem" | "humanities";

export interface GenerateFlashcardParams {
    contentId: string;
    language: string;
    contextMode?: FlashcardContextMode;
    instruction?: string;
    minCriticality?: FlashcardCriticality;
    subjectType?: FlashcardSubjectType;
}

export const getFlashcard = async (contentId: string, language: string): Promise<FlashcardResponse | null> => {
    try {
        const response = await api.get<FlashcardResponse>(`/flashcard/${contentId}`, {
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

export const generateFlashcard = async (
    params: GenerateFlashcardParams
): Promise<GenerateFlashcardResponse> => {
    const response = await api.post<GenerateFlashcardResponse>(
        `/flashcard/${params.contentId}/generate`,
        withLLMOverrides({
            language: params.language,
            context_mode: params.contextMode ?? "both",
            user_instruction: params.instruction ?? "",
            min_criticality: params.minCriticality ?? "low",
            subject_type: params.subjectType ?? "auto",
        })
    );
    return response.data;
};

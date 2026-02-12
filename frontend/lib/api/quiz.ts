/**
 * Quiz APIs - Get and generate quiz questions
 */

import { api } from "./client";
import { withLLMOverrides } from "./ai-overrides";

export interface QuizItem {
    stem: string;
    options: string[];
    answerIndex: number;
    explanation: string;
    sourceCategory: string | null;
    sourceTags: string[];
}

export interface QuizResponse {
    contentId: string;
    language: string;
    items: QuizItem[];
    count: number;
    updatedAt: string | null;
}

export interface GenerateQuizResponse {
    contentId: string;
    taskId: string;
    status: "pending";
    message: string;
}

export type QuizContextMode = "auto" | "subtitle" | "slide" | "both";
export type QuizCriticality = "high" | "medium" | "low";
export type QuizSubjectType = "auto" | "stem" | "humanities";

export interface GenerateQuizParams {
    contentId: string;
    language: string;
    questionCount?: number;
    contextMode?: QuizContextMode;
    instruction?: string;
    minCriticality?: QuizCriticality;
    subjectType?: QuizSubjectType;
}

export const getQuiz = async (contentId: string, language: string): Promise<QuizResponse | null> => {
    try {
        const response = await api.get<QuizResponse>(`/quiz/${contentId}`, {
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

export const generateQuiz = async (
    params: GenerateQuizParams
): Promise<GenerateQuizResponse> => {
    const response = await api.post<GenerateQuizResponse>(
        `/quiz/${params.contentId}/generate`,
        withLLMOverrides({
            language: params.language,
            question_count: params.questionCount ?? 5,
            context_mode: params.contextMode ?? "auto",
            user_instruction: params.instruction ?? "",
            min_criticality: params.minCriticality ?? "medium",
            subject_type: params.subjectType ?? "auto",
        })
    );
    return response.data;
};

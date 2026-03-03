/**
 * Test paper APIs - Get and generate exam-style open-ended questions
 */

import { api } from "./client";
import { withLLMOverrides } from "./ai-overrides";

export interface TestQuestion {
    questionType: string;
    stem: string;
    referenceAnswer: string;
    scoringCriteria: string[];
    bloomLevel: string;
    sourceTimestamp: number | null;
    sourceCategory: string | null;
    sourceTags: string[];
}

export interface TestPaperResponse {
    contentId: string;
    language: string;
    questions: TestQuestion[];
    count: number;
    updatedAt: string | null;
}

export interface GenerateTestPaperResponse {
    contentId: string;
    taskId: string;
    status: "pending";
    message: string;
}

export type TestPaperContextMode = "subtitle" | "slide" | "both";
export type TestPaperCriticality = "high" | "medium" | "low";
export type TestPaperSubjectType = "auto" | "stem" | "humanities";

export interface GenerateTestPaperParams {
    contentId: string;
    language: string;
    contextMode?: TestPaperContextMode;
    instruction?: string;
    minCriticality?: TestPaperCriticality;
    subjectType?: TestPaperSubjectType;
}

export const getTestPaper = async (contentId: string, language: string): Promise<TestPaperResponse | null> => {
    try {
        const response = await api.get<TestPaperResponse>(`/test-paper/${contentId}`, {
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

export const generateTestPaper = async (
    params: GenerateTestPaperParams
): Promise<GenerateTestPaperResponse> => {
    const response = await api.post<GenerateTestPaperResponse>(
        `/test-paper/${params.contentId}/generate`,
        withLLMOverrides({
            language: params.language,
            context_mode: params.contextMode ?? "both",
            user_instruction: params.instruction ?? "",
            min_criticality: params.minCriticality ?? "medium",
            subject_type: params.subjectType ?? "auto",
        })
    );
    return response.data;
};

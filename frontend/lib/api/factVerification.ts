/**
 * Fact Verification APIs - Get and generate fact verification reports
 */

import { api } from "./client";
import { withLLMOverrides } from "./ai-overrides";
import type { FactVerificationReport } from "@/lib/verifyTypes";

export interface GenerateFactVerificationResponse {
    contentId: string;
    taskId: string;
    status: "pending";
    message: string;
}

export const getFactVerificationReport = async (
    contentId: string,
    language: string
): Promise<FactVerificationReport | null> => {
    try {
        const response = await api.get<FactVerificationReport>("/fact-verification", {
            params: { content_id: contentId, language },
        });
        return response.data;
    } catch (error: unknown) {
        if (error && typeof error === "object" && "status" in error && error.status === 404) {
            return null;
        }
        throw error;
    }
};

export interface GenerateFactVerificationParams {
    contentId: string;
    language: string;
}

export const generateFactVerification = async (
    params: GenerateFactVerificationParams
): Promise<GenerateFactVerificationResponse> => {
    const response = await api.post<GenerateFactVerificationResponse>(
        "/fact-verification/generate",
        withLLMOverrides({
            content_id: params.contentId,
            language: params.language,
        })
    );
    return response.data;
};

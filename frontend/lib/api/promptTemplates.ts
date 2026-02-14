import { api } from "./client";
import type {
    CreatePromptTemplatePayload,
    PromptTemplate,
    PromptTemplatesResponse,
} from "./types";

export const listPromptTemplates = async (): Promise<PromptTemplatesResponse> => {
    const response = await api.get<PromptTemplatesResponse>("/prompt-templates");
    return response.data;
};

export const createPromptTemplate = async (
    payload: CreatePromptTemplatePayload,
): Promise<PromptTemplate> => {
    const response = await api.post<PromptTemplate>("/prompt-templates", payload);
    return response.data;
};

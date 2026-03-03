import { api } from "./client";
import type {
    CreatePromptTemplatePayload,
    PromptTemplate,
    PromptTemplateTexts,
    PromptTemplatesResponse,
    UpdatePromptTemplatePayload,
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

export const updatePromptTemplate = async (
    funcId: string,
    implId: string,
    payload: UpdatePromptTemplatePayload,
): Promise<PromptTemplate> => {
    const response = await api.put<PromptTemplate>(
        `/prompt-templates/${funcId}/${implId}`,
        payload,
    );
    return response.data;
};

export const deletePromptTemplate = async (
    funcId: string,
    implId: string,
): Promise<void> => {
    await api.delete(`/prompt-templates/${funcId}/${implId}`);
};

export const getPromptTemplateText = async (
    funcId: string,
    implId: string,
): Promise<PromptTemplateTexts> => {
    const response = await api.get<PromptTemplateTexts>(
        `/prompt-templates/${funcId}/${implId}/text`,
    );
    return response.data;
};

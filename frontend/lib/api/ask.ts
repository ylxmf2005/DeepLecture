/**
 * Ask APIs - Video question answering and conversations
 */

import { api } from "./client";
import { withLLMOverrides } from "./ai-overrides";
import type {
    AskContextItem,
    AskResponse,
    ListAskConversationsResponse,
    AskConversationResponse,
    SummarizeContextResponse,
} from "./types";

export const listAskConversations = async (
    contentId: string
): Promise<ListAskConversationsResponse> => {
    const response = await api.get<ListAskConversationsResponse>("/conversations", {
        params: { contentId },
    });
    return response.data;
};

export const createAskConversation = async (
    contentId: string,
    title?: string
): Promise<AskConversationResponse> => {
    const response = await api.post<AskConversationResponse>("/conversations", {
        content_id: contentId,
        title,
    });
    return response.data;
};

export const getAskConversation = async (
    contentId: string,
    conversationId: string
): Promise<AskConversationResponse> => {
    const response = await api.get<AskConversationResponse>(`/conversations/${conversationId}`, {
        params: { contentId },
    });
    return response.data;
};

export const deleteAskConversation = async (
    contentId: string,
    conversationId: string
): Promise<void> => {
    await api.delete(`/conversations/${conversationId}`, {
        data: { content_id: contentId },
    });
};

export interface AskVideoQuestionParams {
    contentId: string;
    conversationId: string;
    message: string;
    context: AskContextItem[];
    learnerProfile?: string;
    subtitleContextWindowSeconds?: number;
}

export const askVideoQuestion = async (
    params: AskVideoQuestionParams
): Promise<AskResponse> => {
    const response = await api.post<AskResponse>(
        `/conversations/${params.conversationId}/messages`,
        withLLMOverrides({
            content_id: params.contentId,
            message: params.message,
            context: params.context,
            learner_profile: params.learnerProfile,
            subtitle_context_window_seconds: params.subtitleContextWindowSeconds,
        })
    );
    return response.data;
};

export interface SummarizeContextParams {
    context: AskContextItem[];
    learnerProfile?: string;
}

export const summarizeContext = async (
    params: SummarizeContextParams
): Promise<SummarizeContextResponse> => {
    const response = await api.post<SummarizeContextResponse>(
        "/summaries",
        withLLMOverrides({
            context: params.context,
            learner_profile: params.learnerProfile,
        })
    );
    return response.data;
};

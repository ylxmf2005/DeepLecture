/**
 * Notes APIs - Get, save, and generate video notes
 */

import { api } from "./client";
import { withLLMOverrides } from "./ai-overrides";
import type { VideoNoteResponse, NoteContextMode, GenerateVideoNoteResponse } from "./types";

export const getVideoNote = async (contentId: string): Promise<VideoNoteResponse> => {
    const response = await api.get<VideoNoteResponse>("/notes", {
        params: { contentId },
    });
    return response.data;
};

export const saveVideoNote = async (
    contentId: string,
    content: string
): Promise<VideoNoteResponse> => {
    const response = await api.post<VideoNoteResponse>("/notes", {
        content_id: contentId,
        content,
    });
    return response.data;
};

export interface GenerateVideoNoteParams {
    contentId: string;
    language: string;
    contextMode?: NoteContextMode;
    instruction?: string;
    learnerProfile?: string;
    maxParts?: number;
}

export const generateVideoNote = async (
    params: GenerateVideoNoteParams
): Promise<GenerateVideoNoteResponse> => {
    const response = await api.post<GenerateVideoNoteResponse>(
        "/notes/generate",
        withLLMOverrides({
            content_id: params.contentId,
            language: params.language,
            context_mode: params.contextMode ?? "auto",
            user_instruction: params.instruction ?? "",
            learner_profile: params.learnerProfile ?? "",
            max_parts: params.maxParts,
        })
    );
    return response.data;
};

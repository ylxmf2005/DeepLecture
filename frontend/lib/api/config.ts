/**
 * Config APIs - Language settings, Live2D models, LLM/TTS models, Note defaults
 */

import { api } from "./client";
import type {
    LanguageSettings,
    Live2DModel,
    NoteDefaultsResponse,
    AppConfigResponse,
} from "./types";

export const getLanguageSettings = async (): Promise<LanguageSettings> => {
    const response = await api.get<LanguageSettings>("/languages");
    return response.data;
};

export const getLive2DModels = async (): Promise<Live2DModel[]> => {
    const response = await api.get<{ models: Live2DModel[] }>("/live2d/models");
    return response.data.models;
};

export const getNoteDefaults = async (): Promise<NoteDefaultsResponse> => {
    const response = await api.get<NoteDefaultsResponse>("/note-defaults");
    return response.data;
};

export const getAppConfig = async (): Promise<AppConfigResponse> => {
    const response = await api.get<AppConfigResponse>("/config");
    return response.data;
};

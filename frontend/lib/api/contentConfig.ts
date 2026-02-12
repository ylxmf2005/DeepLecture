/**
 * Content Config API - Per-video configuration CRUD
 */

import { api } from "./client";
import type { PerVideoConfig } from "@/stores/types";

export async function getContentConfig(contentId: string): Promise<PerVideoConfig> {
    const response = await api.get<PerVideoConfig>(`/content/${contentId}/config`);
    return response.data;
}

export async function putContentConfig(
    contentId: string,
    config: PerVideoConfig
): Promise<PerVideoConfig> {
    const response = await api.put<PerVideoConfig>(`/content/${contentId}/config`, config);
    return response.data;
}

export async function deleteContentConfig(contentId: string): Promise<void> {
    await api.delete(`/content/${contentId}/config`);
}

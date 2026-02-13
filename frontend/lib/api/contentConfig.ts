/**
 * Content Config API - Per-video configuration CRUD
 */

import { api } from "./client";
import type { PerVideoConfig } from "@/stores/types";
import { normalizeConfigPayload, serializeConfigPayload } from "./configSerialization";

export async function getContentConfig(contentId: string): Promise<PerVideoConfig> {
    const response = await api.get<unknown>(`/content/${contentId}/config`);
    return normalizeConfigPayload(response.data);
}

export async function putContentConfig(
    contentId: string,
    config: PerVideoConfig
): Promise<PerVideoConfig> {
    const response = await api.put<unknown>(`/content/${contentId}/config`, serializeConfigPayload(config));
    return normalizeConfigPayload(response.data);
}

export async function deleteContentConfig(contentId: string): Promise<void> {
    await api.delete(`/content/${contentId}/config`);
}

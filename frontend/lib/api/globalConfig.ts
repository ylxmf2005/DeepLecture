/**
 * Global Config API - service-level configuration CRUD
 */

import { api } from "./client";
import type { DeepPartial, GlobalSettings } from "@/stores/types";
import { normalizeConfigPayload, serializeConfigPayload } from "./configSerialization";

type GlobalConfigPatch = DeepPartial<GlobalSettings>;

export async function getGlobalConfig(): Promise<GlobalConfigPatch> {
    const response = await api.get<unknown>("/global-config");
    return normalizeConfigPayload(response.data);
}

export async function putGlobalConfig(config: GlobalConfigPatch): Promise<GlobalConfigPatch> {
    const response = await api.put<unknown>("/global-config", serializeConfigPayload(config));
    return normalizeConfigPayload(response.data);
}

export async function deleteGlobalConfig(): Promise<void> {
    await api.delete("/global-config");
}

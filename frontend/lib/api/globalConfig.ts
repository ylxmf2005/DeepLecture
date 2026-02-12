/**
 * Global Config API - service-level configuration CRUD
 */

import { api } from "./client";
import type { GlobalSettings } from "@/stores/types";

export async function getGlobalConfig(): Promise<Partial<GlobalSettings>> {
    const response = await api.get<Partial<GlobalSettings>>("/global-config");
    return response.data;
}

export async function putGlobalConfig(config: Partial<GlobalSettings>): Promise<Partial<GlobalSettings>> {
    const response = await api.put<Partial<GlobalSettings>>("/global-config", config);
    return response.data;
}

export async function deleteGlobalConfig(): Promise<void> {
    await api.delete("/global-config");
}

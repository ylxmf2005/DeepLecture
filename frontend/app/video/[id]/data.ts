/**
 * Server-side data fetching for video page
 * Uses shared transform utilities for consistent snake_case ↔ camelCase conversion
 */

import type { ContentItem, VoiceoverEntry } from "@/lib/api";
import { API_BASE_URL } from "@/lib/api/baseUrl";
import { unwrapApiResponse } from "@/lib/api/transform";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";

const log = logger.scope("VideoDataServer");

/**
 * Fetch content metadata from backend (server-side)
 */
export async function getContentMetadataServer(contentId: string): Promise<ContentItem | null> {
    try {
        const response = await fetch(`${API_BASE_URL}/api/content/${contentId}`, {
            cache: "no-store",
        });

        if (!response.ok) {
            if (response.status === 404) {
                return null;
            }
            throw new Error(`Failed to fetch content: ${response.status}`);
        }

        const raw = await response.json();
        return unwrapApiResponse<ContentItem>(raw);
    } catch (error) {
        log.error("Failed to fetch content metadata", toError(error), { contentId });
        return null;
    }
}

/**
 * Fetch voiceovers list from backend (server-side)
 */
export async function listVoiceoversServer(videoId: string): Promise<VoiceoverEntry[]> {
    try {
        const response = await fetch(`${API_BASE_URL}/api/content/${videoId}/voiceovers`, {
            cache: "no-store",
        });

        if (!response.ok) {
            if (response.status === 404) {
                return [];
            }
            throw new Error(`Failed to fetch voiceovers: ${response.status}`);
        }

        const raw = await response.json();
        const data = unwrapApiResponse<{ voiceovers: VoiceoverEntry[] }>(raw);
        return data.voiceovers || [];
    } catch (error) {
        log.error("Failed to fetch voiceovers", toError(error), { videoId });
        return [];
    }
}

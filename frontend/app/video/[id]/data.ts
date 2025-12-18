/**
 * Server-side data fetching for video page
 * Uses shared transform utilities for consistent snake_case ↔ camelCase conversion
 */

import type { ContentItem, VoiceoverEntry } from "@/lib/api";
import { unwrapApiResponse } from "@/lib/api/transform";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:11393";

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
        console.error("[Server] Failed to fetch content metadata:", error);
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
        console.error("[Server] Failed to fetch voiceovers:", error);
        return [];
    }
}

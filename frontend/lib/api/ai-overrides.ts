/**
 * AI Overrides - Centralized injection point for AI model/prompt settings
 *
 * This module provides a single source of truth for injecting AI settings
 * into API requests. All generation-related API calls should use this.
 *
 * Per-video config is merged via a module-level reference set by useContentConfig.
 * This avoids threading resolvedConfig through 12+ API functions.
 */

import { useGlobalSettingsStore } from "@/stores/useGlobalSettingsStore";
import type { PerVideoConfig } from "@/stores/types";

export interface AIOverrides {
    llm_model?: string;
    tts_model?: string;
    prompts?: Record<string, string>;
}

// ─── Per-Video Config (module-level reference) ──────────────────────────────

/**
 * Module-level reference to the current video's per-video config.
 * Set by useContentConfig on mount, cleared on unmount.
 * All withLLMOverrides/withTTSOverrides calls automatically merge this.
 */
let currentVideoConfig: PerVideoConfig | null = null;

export function setCurrentVideoConfig(config: PerVideoConfig | null): void {
    currentVideoConfig = config;
}

export function getCurrentVideoConfig(): PerVideoConfig | null {
    return currentVideoConfig;
}

// ─── Override Resolution ────────────────────────────────────────────────────

/**
 * Get current AI overrides from global settings + per-video config.
 * Per-video overrides take precedence over global defaults.
 * Returns only non-null/non-empty values to let backend use defaults.
 */
export function getAIOverrides(): AIOverrides {
    const { ai } = useGlobalSettingsStore.getState();
    const overrides: AIOverrides = {};

    // Per-video overrides take precedence over global (nested shape)
    const effectiveLlmModel = currentVideoConfig?.ai?.llmModel ?? ai.llmModel;
    const effectiveTtsModel = currentVideoConfig?.ai?.ttsModel ?? ai.ttsModel;

    if (effectiveLlmModel) {
        overrides.llm_model = effectiveLlmModel;
    }

    if (effectiveTtsModel) {
        overrides.tts_model = effectiveTtsModel;
    }

    // Merge prompts: global first, per-video overrides on top
    const mergedPrompts = {
        ...ai.prompts,
        ...(currentVideoConfig?.ai?.prompts ?? {}),
    };

    if (Object.keys(mergedPrompts).length > 0) {
        overrides.prompts = mergedPrompts;
    }

    return overrides;
}

/**
 * Get language overrides (global + per-video merged).
 * Used by API functions that need source/target language.
 */
export function getLanguageOverrides(): { source_language?: string; target_language?: string } {
    const { language } = useGlobalSettingsStore.getState();
    const result: { source_language?: string; target_language?: string } = {};

    const effectiveSource = currentVideoConfig?.language?.original ?? language.original;
    const effectiveTarget = currentVideoConfig?.language?.translated ?? language.translated;

    if (effectiveSource) {
        result.source_language = effectiveSource;
    }
    if (effectiveTarget) {
        result.target_language = effectiveTarget;
    }

    return result;
}

/**
 * Get LLM-only overrides (for text generation tasks).
 */
export function getLLMOverrides(): Pick<AIOverrides, "llm_model" | "prompts"> {
    const full = getAIOverrides();
    const { tts_model: _, ...llmOnly } = full;
    return llmOnly;
}

/**
 * Get TTS-only overrides (for audio generation tasks).
 */
export function getTTSOverrides(): Pick<AIOverrides, "tts_model"> {
    const { ai } = useGlobalSettingsStore.getState();
    const effectiveTtsModel = currentVideoConfig?.ai?.ttsModel ?? ai.ttsModel;
    return effectiveTtsModel ? { tts_model: effectiveTtsModel } : {};
}

/**
 * Merge AI overrides into a request body.
 * Spreads overrides at the end to ensure they're included.
 */
export function withAIOverrides<T extends object>(body: T): T & AIOverrides {
    return { ...body, ...getAIOverrides() };
}

/**
 * Merge LLM overrides only (no TTS).
 */
export function withLLMOverrides<T extends object>(body: T): T & Pick<AIOverrides, "llm_model" | "prompts"> {
    return { ...body, ...getLLMOverrides() };
}

/**
 * Merge TTS overrides only (no LLM).
 */
export function withTTSOverrides<T extends object>(body: T): T & Pick<AIOverrides, "tts_model"> {
    return { ...body, ...getTTSOverrides() };
}

/**
 * AI Overrides - Centralized injection point for AI model/prompt settings
 *
 * This module provides a single source of truth for injecting AI settings
 * into API requests. All generation-related API calls should use this.
 */

import { useGlobalSettingsStore } from "@/stores/useGlobalSettingsStore";

export interface AIOverrides {
    llm_model?: string;
    tts_model?: string;
    prompts?: Record<string, string>;
}

/**
 * Get current AI overrides from global settings store.
 * Returns only non-null/non-empty values to let backend use defaults.
 */
export function getAIOverrides(): AIOverrides {
    const { ai } = useGlobalSettingsStore.getState();
    const overrides: AIOverrides = {};

    if (ai.llmModel) {
        overrides.llm_model = ai.llmModel;
    }

    if (ai.ttsModel) {
        overrides.tts_model = ai.ttsModel;
    }

    if (Object.keys(ai.prompts).length > 0) {
        overrides.prompts = ai.prompts;
    }

    return overrides;
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
    return ai.ttsModel ? { tts_model: ai.ttsModel } : {};
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

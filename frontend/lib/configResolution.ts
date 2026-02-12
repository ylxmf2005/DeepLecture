/**
 * Config Resolution — generic deep merge for cascading settings.
 *
 * Merges per-video overrides onto global defaults:
 * - Per-video values win over global
 * - Missing per-video fields fall through to global
 * - Prompts (Record<string, string>) merge at key level
 */

import type { GlobalSettings, PerVideoConfig, ResolvedTaskConfig } from "@/stores/types";

// ─── Deep Merge ──────────────────────────────────────────────────────────────

type AnyObject = Record<string, unknown>;

/**
 * Recursively merge sparse overrides onto a fully populated defaults object.
 * - Leaf values: override wins if defined (not undefined)
 * - Record<string, string> (prompts): key-level merge
 * - Nested objects: recurse
 */
function deepMerge(defaults: AnyObject, overrides: AnyObject): AnyObject {
    const result = { ...defaults };

    for (const key of Object.keys(overrides)) {
        const overrideVal = overrides[key];
        if (overrideVal === undefined) continue;

        const defaultVal = defaults[key];

        // Record<string, string> (like prompts) — merge at key level
        if (
            isPlainObject(defaultVal) &&
            isPlainObject(overrideVal) &&
            isStringRecord(defaultVal) &&
            isStringRecord(overrideVal)
        ) {
            result[key] = { ...defaultVal, ...overrideVal };
            continue;
        }

        // Nested object — recurse
        if (isPlainObject(defaultVal) && isPlainObject(overrideVal)) {
            result[key] = deepMerge(
                defaultVal as AnyObject,
                overrideVal as AnyObject,
            );
            continue;
        }

        // Leaf value — override wins
        result[key] = overrideVal;
    }

    return result;
}

function isPlainObject(val: unknown): val is Record<string, unknown> {
    return typeof val === "object" && val !== null && !Array.isArray(val);
}

function isStringRecord(obj: unknown): obj is Record<string, string> {
    if (typeof obj !== "object" || obj === null || Array.isArray(obj)) return false;
    return Object.values(obj as Record<string, unknown>).every(
        (v) => typeof v === "string",
    );
}

// ─── Public API ──────────────────────────────────────────────────────────────

/**
 * Resolve effective settings by merging global + per-video overrides.
 * Returns a fully populated GlobalSettings.
 */
export function resolveSettings(
    global: GlobalSettings,
    perVideo: PerVideoConfig | null,
): GlobalSettings {
    if (!perVideo || Object.keys(perVideo).length === 0) return global;
    return deepMerge(
        global as unknown as AnyObject,
        perVideo as unknown as AnyObject,
    ) as unknown as GlobalSettings;
}

/**
 * Extract flat task-config from resolved settings.
 * Used for backend API request bodies that expect the flat shape.
 */
export function toTaskConfig(resolved: GlobalSettings): ResolvedTaskConfig {
    return {
        sourceLanguage: resolved.language.original,
        targetLanguage: resolved.language.translated,
        llmModel: resolved.ai.llmModel,
        ttsModel: resolved.ai.ttsModel,
        prompts: resolved.ai.prompts,
        learnerProfile: resolved.learnerProfile,
        noteContextMode: resolved.note.contextMode,
    };
}

/**
 * Check if a specific field path is overridden in per-video config.
 * Supports dot-separated paths like "playback.autoPauseOnLeave" or "ai.llmModel".
 */
export function isFieldOverridden(
    perVideo: PerVideoConfig | null,
    path: string,
): boolean {
    if (!perVideo) return false;

    const parts = path.split(".");
    let current: unknown = perVideo;

    for (const part of parts) {
        if (current === null || current === undefined || typeof current !== "object") {
            return false;
        }
        current = (current as Record<string, unknown>)[part];
    }

    return current !== undefined;
}

/**
 * Count the number of overridden leaf fields in per-video config.
 */
export function countOverrides(perVideo: PerVideoConfig | null): number {
    if (!perVideo) return 0;
    return countLeaves(perVideo);
}

function countLeaves(obj: unknown): number {
    if (obj === null || obj === undefined) return 0;
    if (typeof obj !== "object" || Array.isArray(obj)) return 1;

    let count = 0;
    for (const value of Object.values(obj as Record<string, unknown>)) {
        if (value === undefined) continue;
        if (typeof value === "object" && value !== null && !Array.isArray(value)) {
            // Check if it's a Record<string, string> (prompts) — count as 1
            if (isStringRecord(value)) {
                count += 1;
                continue;
            }
            count += countLeaves(value);
        } else {
            count += 1;
        }
    }
    return count;
}

/**
 * Set a value at a dot-separated path in a per-video config object.
 * Returns a new object (immutable).
 */
export function setOverrideField(
    perVideo: PerVideoConfig,
    path: string,
    value: unknown,
): PerVideoConfig {
    const parts = path.split(".");
    if (parts.length === 1) {
        return { ...perVideo, [parts[0]]: value };
    }

    const [head, ...rest] = parts;
    const nested = (perVideo as Record<string, unknown>)[head];
    const nestedObj = (typeof nested === "object" && nested !== null) ? nested : {};

    return {
        ...perVideo,
        [head]: setOverrideField(
            nestedObj as PerVideoConfig,
            rest.join("."),
            value,
        ),
    };
}

/**
 * Remove a value at a dot-separated path from a per-video config object.
 * Cleans up empty parent objects.
 * Returns a new object (immutable).
 */
export function clearOverrideField(
    perVideo: PerVideoConfig,
    path: string,
): PerVideoConfig {
    const parts = path.split(".");
    if (parts.length === 1) {
        const { [parts[0]]: _, ...rest } = perVideo as Record<string, unknown>;
        return rest as PerVideoConfig;
    }

    const [head, ...tail] = parts;
    const nested = (perVideo as Record<string, unknown>)[head];
    if (typeof nested !== "object" || nested === null) return perVideo;

    const cleaned = clearOverrideField(
        nested as PerVideoConfig,
        tail.join("."),
    );

    // If the nested object is now empty, remove the parent key too
    if (Object.keys(cleaned).length === 0) {
        const { [head]: _, ...rest } = perVideo as Record<string, unknown>;
        return rest as PerVideoConfig;
    }

    return { ...perVideo, [head]: cleaned };
}

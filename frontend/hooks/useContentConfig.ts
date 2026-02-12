"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";
import { getContentConfig, putContentConfig, deleteContentConfig } from "@/lib/api/contentConfig";
import { setCurrentVideoConfig } from "@/lib/api/ai-overrides";
import { useGlobalSettingsStore } from "@/stores/useGlobalSettingsStore";
import type { GlobalSettings, PerVideoConfig, ResolvedTaskConfig } from "@/stores/types";
import { resolveSettings, toTaskConfig, isFieldOverridden as checkFieldOverridden, clearOverrideField } from "@/lib/configResolution";

const log = logger.scope("useContentConfig");

const DEBOUNCE_MS = 800;

interface UseContentConfigReturn {
    /** Sparse per-video overrides (only fields explicitly set) */
    overrides: PerVideoConfig;
    /** Fully resolved settings (global + per-video merged) */
    resolved: GlobalSettings;
    /** Flat task config for API requests */
    resolvedTaskConfig: ResolvedTaskConfig;
    /** Whether the initial fetch is in progress */
    loading: boolean;
    /** Update one or more per-video override fields */
    setOverrides: (updates: PerVideoConfig) => void;
    /** Remove a specific override field path (reset to global) */
    clearOverride: (field: string) => void;
    /** Remove all per-video overrides */
    clearAllOverrides: () => Promise<void>;
    /** Whether a field path is explicitly overridden per-video */
    isOverridden: (field: string) => boolean;
}

export function useContentConfig(contentId: string): UseContentConfigReturn {
    const [overrides, setOverridesState] = useState<PerVideoConfig>({});
    const [loading, setLoading] = useState(true);
    const pendingPutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const latestOverridesRef = useRef<PerVideoConfig>({});

    // Keep ref in sync for debounced flush
    useEffect(() => {
        latestOverridesRef.current = overrides;
    }, [overrides]);

    // Flush pending PUT on unmount
    useEffect(() => {
        return () => {
            if (pendingPutRef.current) {
                clearTimeout(pendingPutRef.current);
                pendingPutRef.current = null;
                // Fire-and-forget final save
                const finalOverrides = latestOverridesRef.current;
                putContentConfig(contentId, finalOverrides).catch((error) => {
                    log.error("Failed to flush pending config on unmount", toError(error));
                });
            }
            setCurrentVideoConfig(null);
        };
    }, [contentId]);

    // Fetch per-video config on mount
    useEffect(() => {
        let cancelled = false;

        const fetchConfig = async () => {
            try {
                const config = await getContentConfig(contentId);
                if (!cancelled) {
                    setOverridesState(config);
                    setCurrentVideoConfig(config);
                }
            } catch (error) {
                log.error("Failed to fetch video config", toError(error), { contentId });
                if (!cancelled) {
                    setOverridesState({});
                    setCurrentVideoConfig(null);
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        };

        fetchConfig();
        return () => {
            cancelled = true;
        };
    }, [contentId]);

    // Resolve config: merge global + per-video
    const globalSettings = useGlobalSettingsStore();
    const resolved = useMemo<GlobalSettings>(
        () => resolveSettings(globalSettings, overrides),
        [globalSettings, overrides]
    );
    const resolvedTaskConfig = useMemo<ResolvedTaskConfig>(
        () => toTaskConfig(resolved),
        [resolved]
    );

    // Debounced PUT helper
    const debouncedPut = useCallback(
        (newOverrides: PerVideoConfig) => {
            if (pendingPutRef.current) {
                clearTimeout(pendingPutRef.current);
            }
            pendingPutRef.current = setTimeout(async () => {
                pendingPutRef.current = null;
                try {
                    await putContentConfig(contentId, newOverrides);
                } catch (error) {
                    log.error("Failed to save video config", toError(error), { contentId });
                }
            }, DEBOUNCE_MS);
        },
        [contentId]
    );

    const setOverrides = useCallback(
        (updates: PerVideoConfig) => {
            const current = latestOverridesRef.current;
            // Deep merge updates into current overrides
            const newOverrides = deepMergeOverrides(current, updates);
            setOverridesState(newOverrides);
            setCurrentVideoConfig(newOverrides);
            debouncedPut(newOverrides);
        },
        [debouncedPut]
    );

    const clearOverride = useCallback(
        (field: string) => {
            const newOverrides = clearOverrideField(latestOverridesRef.current, field);
            setOverridesState(newOverrides);
            setCurrentVideoConfig(Object.keys(newOverrides).length > 0 ? newOverrides : null);
            debouncedPut(newOverrides);
        },
        [debouncedPut]
    );

    const clearAllOverrides = useCallback(async () => {
        // Cancel any pending debounced PUT
        if (pendingPutRef.current) {
            clearTimeout(pendingPutRef.current);
            pendingPutRef.current = null;
        }
        setOverridesState({});
        setCurrentVideoConfig(null);
        try {
            await deleteContentConfig(contentId);
        } catch (error) {
            log.error("Failed to clear all overrides", toError(error), { contentId });
        }
    }, [contentId]);

    const isOverridden = useCallback(
        (field: string) => checkFieldOverridden(overrides, field),
        [overrides]
    );

    return { overrides, resolved, resolvedTaskConfig, loading, setOverrides, clearOverride, clearAllOverrides, isOverridden };
}

/**
 * Deep merge two PerVideoConfig objects.
 * Nested objects are merged recursively; leaves are overwritten.
 */
function deepMergeOverrides(base: PerVideoConfig, updates: PerVideoConfig): PerVideoConfig {
    const result = { ...base };
    for (const [key, value] of Object.entries(updates)) {
        const existing = (result as Record<string, unknown>)[key];
        if (
            typeof existing === "object" && existing !== null && !Array.isArray(existing) &&
            typeof value === "object" && value !== null && !Array.isArray(value)
        ) {
            (result as Record<string, unknown>)[key] = { ...existing, ...value };
        } else {
            (result as Record<string, unknown>)[key] = value;
        }
    }
    return result;
}

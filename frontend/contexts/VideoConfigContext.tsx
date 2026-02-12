"use client";

/**
 * VideoConfigContext — per-video configuration provider.
 *
 * Wraps the video page to provide resolved settings (global + per-video merged).
 * Selector hooks in useGlobalSettingsStore check this context and transparently
 * return resolved values when inside a VideoConfigProvider, global values otherwise.
 *
 * This is the "scope-aware" injection mechanism described in the unified settings plan.
 */

import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useRef,
    useState,
    type ReactNode,
} from "react";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";
import { getContentConfig, putContentConfig, deleteContentConfig } from "@/lib/api/contentConfig";
import { setCurrentVideoConfig } from "@/lib/api/ai-overrides";
import { useGlobalSettingsStore } from "@/stores/useGlobalSettingsStore";
import type { GlobalSettings, PerVideoConfig } from "@/stores/types";
import {
    resolveSettings,
    isFieldOverridden as checkFieldOverridden,
    countOverrides as countOverrideFields,
    setOverrideField,
    clearOverrideField,
} from "@/lib/configResolution";

const log = logger.scope("VideoConfigContext");

const DEBOUNCE_MS = 800;

// ─── Context Shape ───────────────────────────────────────────────────────────

export interface VideoConfigContextValue {
    /** Sparse per-video overrides (only fields explicitly set) */
    overrides: PerVideoConfig;
    /** Fully resolved settings (global + per-video merged) */
    resolved: GlobalSettings;
    /** Whether the initial fetch is in progress */
    loading: boolean;
    /** Content ID for the current video */
    contentId: string;
    /** Update per-video overrides (deep merged into existing) */
    setOverrides: (updates: PerVideoConfig) => void;
    /** Set a specific field path override */
    setField: (path: string, value: unknown) => void;
    /** Clear a specific field path override (reset to global) */
    clearField: (path: string) => void;
    /** Clear all per-video overrides */
    clearAll: () => Promise<void>;
    /** Check if a field path is explicitly overridden */
    isOverridden: (path: string) => boolean;
    /** Count of overridden leaf fields */
    overrideCount: number;
}

const VideoConfigContext = createContext<VideoConfigContextValue | null>(null);

// ─── Provider ────────────────────────────────────────────────────────────────

export function VideoConfigProvider({
    contentId,
    children,
}: {
    contentId: string;
    children: ReactNode;
}) {
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

    // Resolve: global + per-video
    const globalSettings = useGlobalSettingsStore();
    const resolved = useMemo<GlobalSettings>(
        () => resolveSettings(globalSettings, overrides),
        [globalSettings, overrides],
    );

    // Debounced PUT
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
        [contentId],
    );

    const applyOverrides = useCallback(
        (newOverrides: PerVideoConfig) => {
            setOverridesState(newOverrides);
            setCurrentVideoConfig(Object.keys(newOverrides).length > 0 ? newOverrides : null);
            debouncedPut(newOverrides);
        },
        [debouncedPut],
    );

    const setOverrides = useCallback(
        (updates: PerVideoConfig) => {
            const current = latestOverridesRef.current;
            const merged = deepMergeOverrides(current, updates);
            applyOverrides(merged);
        },
        [applyOverrides],
    );

    const setField = useCallback(
        (path: string, value: unknown) => {
            const newOverrides = setOverrideField(latestOverridesRef.current, path, value);
            applyOverrides(newOverrides);
        },
        [applyOverrides],
    );

    const clearField = useCallback(
        (path: string) => {
            const newOverrides = clearOverrideField(latestOverridesRef.current, path);
            applyOverrides(newOverrides);
        },
        [applyOverrides],
    );

    const clearAll = useCallback(async () => {
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
        (path: string) => checkFieldOverridden(overrides, path),
        [overrides],
    );

    const overrideCount = useMemo(
        () => countOverrideFields(overrides),
        [overrides],
    );

    const value = useMemo<VideoConfigContextValue>(
        () => ({
            overrides,
            resolved,
            loading,
            contentId,
            setOverrides,
            setField,
            clearField,
            clearAll,
            isOverridden,
            overrideCount,
        }),
        [overrides, resolved, loading, contentId, setOverrides, setField, clearField, clearAll, isOverridden, overrideCount],
    );

    return (
        <VideoConfigContext.Provider value={value}>
            {children}
        </VideoConfigContext.Provider>
    );
}

// ─── Hooks ───────────────────────────────────────────────────────────────────

/**
 * Access per-video config context. Throws if used outside a VideoConfigProvider.
 */
export function useVideoConfig(): VideoConfigContextValue {
    const ctx = useContext(VideoConfigContext);
    if (!ctx) {
        throw new Error("useVideoConfig must be used within a VideoConfigProvider");
    }
    return ctx;
}

/**
 * Access per-video config context if available (returns null on home page).
 * This is used by scope-aware selector hooks to transparently resolve settings.
 */
export function useVideoConfigOptional(): VideoConfigContextValue | null {
    return useContext(VideoConfigContext);
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

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

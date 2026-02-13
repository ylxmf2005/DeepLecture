"use client";

import { useEffect, useRef } from "react";
import { useGlobalSettingsStore } from "@/stores";
import { PerformanceMonitor, logger } from "@/shared/infrastructure";

const log = logger.scope("AppInitializer");

/**
 * AppInitializer - Handles one-time app initialization tasks on mount.
 *
 * Current responsibilities:
 * - Loading language settings from server
 * - Performance monitoring (Core Web Vitals)
 *
 * @remarks
 * This component should be placed near the root of the app,
 * inside client-side providers but outside of page-specific logic.
 * Initialization failures are non-critical and fall back to defaults.
 */
export function AppInitializer({ children }: { children: React.ReactNode }) {
    const loadGlobalConfigFromServer = useGlobalSettingsStore((s) => s.loadGlobalConfigFromServer);
    const initializedRef = useRef(false);

    useEffect(() => {
        // Only run once per app lifecycle
        if (initializedRef.current) return;
        initializedRef.current = true;

        loadGlobalConfigFromServer().catch((error) => {
            // Non-critical failure - app continues with default global settings
            log.warn("Failed to load global settings", { error: error instanceof Error ? error.message : String(error) });
        });
    }, [loadGlobalConfigFromServer]);

    return (
        <>
            <PerformanceMonitor />
            {children}
        </>
    );
}

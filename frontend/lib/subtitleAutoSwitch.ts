import type { SubtitleDisplayMode } from "@/stores/types";

export interface AutoSwitchState {
    /** Whether user was manually on a non-target mode before auto-switch */
    previousMode: SubtitleDisplayMode | null;
    /** Whether the last mode change was due to auto-switch (vs manual user action) */
    wasAutoSwitched: boolean;
}

export interface AutoSwitchContext {
    enabled: boolean;
    hasTranslation: boolean;
    currentMode: SubtitleDisplayMode;
    state: AutoSwitchState;
}

/**
 * Determines the subtitle mode to switch to when page becomes hidden.
 * Returns null if no switch should occur.
 */
export function getAutoSwitchModeOnHide(
    ctx: Omit<AutoSwitchContext, "state">
): SubtitleDisplayMode | null {
    const { enabled, hasTranslation, currentMode } = ctx;

    // Don't switch if disabled or no translation available
    if (!enabled || !hasTranslation) {
        return null;
    }

    // Already on target - no need to switch
    if (currentMode === "target") {
        return null;
    }

    // Switch to target for background listening
    return "target";
}

/**
 * Determines the subtitle mode to restore when page becomes visible.
 * Returns null if no restore should occur.
 */
export function getAutoSwitchModeOnShow(
    ctx: AutoSwitchContext
): SubtitleDisplayMode | null {
    const { enabled, currentMode, state } = ctx;

    // Don't restore if disabled or wasn't auto-switched
    if (!enabled || !state.wasAutoSwitched) {
        return null;
    }

    // Don't restore if user manually changed mode while away
    // (detected by currentMode no longer being target)
    if (currentMode !== "target") {
        return null;
    }

    // Restore previous mode if we have one
    return state.previousMode;
}

/**
 * Creates initial auto-switch state.
 */
export function createAutoSwitchState(): AutoSwitchState {
    return {
        previousMode: null,
        wasAutoSwitched: false,
    };
}

/**
 * Updates state when auto-switching on hide.
 */
export function updateStateOnAutoSwitch(
    state: AutoSwitchState,
    previousMode: SubtitleDisplayMode
): AutoSwitchState {
    return {
        previousMode,
        wasAutoSwitched: true,
    };
}

/**
 * Resets state after restore or manual override.
 */
export function resetAutoSwitchState(): AutoSwitchState {
    return {
        previousMode: null,
        wasAutoSwitched: false,
    };
}

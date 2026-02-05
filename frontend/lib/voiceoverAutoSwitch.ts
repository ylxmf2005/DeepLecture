/**
 * Pure functions for voiceover auto-switching on page visibility changes.
 * Follows the same pattern as subtitleAutoSwitch.ts for consistency.
 */

export interface VoiceoverAutoSwitchState {
    /** The voiceover ID that was active before auto-switch (null = video original) */
    previousVoiceoverId: string | null;
    /** Whether the last voiceover change was due to auto-switch */
    wasAutoSwitched: boolean;
}

export interface VoiceoverAutoSwitchContext {
    enabled: boolean;
    /** Currently active voiceover ID (null = video original audio) */
    selectedVoiceoverId: string | null;
    /** Quick toggle preset: Original track */
    originalVoiceoverId: string | null;
    /** Quick toggle preset: Translated track (null = not configured) */
    translatedVoiceoverId: string | null;
    state: VoiceoverAutoSwitchState;
}

/**
 * Determines the voiceover to switch to when page becomes hidden.
 * Returns the voiceover ID to switch to, or undefined if no switch should occur.
 * (Using undefined instead of null because null is a valid voiceover value meaning "video original")
 */
export function getAutoSwitchVoiceoverOnHide(
    ctx: Omit<VoiceoverAutoSwitchContext, "state">
): string | null | undefined {
    const { enabled, selectedVoiceoverId, originalVoiceoverId, translatedVoiceoverId } = ctx;

    // Don't switch if disabled or no translated track configured
    if (!enabled || translatedVoiceoverId == null) {
        return undefined;
    }

    // Already on translated track - no need to switch
    if (selectedVoiceoverId === translatedVoiceoverId) {
        return undefined;
    }

    // Only switch if currently on the original preset track
    if (selectedVoiceoverId !== originalVoiceoverId) {
        return undefined;
    }

    // Switch to translated track for background listening
    return translatedVoiceoverId;
}

/**
 * Determines the voiceover to restore when page becomes visible.
 * Returns the voiceover ID to restore, or undefined if no restore should occur.
 */
export function getAutoSwitchVoiceoverOnShow(
    ctx: VoiceoverAutoSwitchContext
): string | null | undefined {
    const { enabled, selectedVoiceoverId, translatedVoiceoverId, state } = ctx;

    // Don't restore if disabled or wasn't auto-switched
    if (!enabled || !state.wasAutoSwitched) {
        return undefined;
    }

    // Don't restore if user manually changed voiceover while away
    if (selectedVoiceoverId !== translatedVoiceoverId) {
        return undefined;
    }

    // Restore previous voiceover
    return state.previousVoiceoverId;
}

export function createVoiceoverAutoSwitchState(): VoiceoverAutoSwitchState {
    return {
        previousVoiceoverId: null,
        wasAutoSwitched: false,
    };
}

export function updateStateOnVoiceoverAutoSwitch(
    previousVoiceoverId: string | null
): VoiceoverAutoSwitchState {
    return {
        previousVoiceoverId,
        wasAutoSwitched: true,
    };
}

export function resetVoiceoverAutoSwitchState(): VoiceoverAutoSwitchState {
    return {
        previousVoiceoverId: null,
        wasAutoSwitched: false,
    };
}

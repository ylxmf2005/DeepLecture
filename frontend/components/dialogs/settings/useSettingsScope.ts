"use client";

/**
 * useSettingsScope — provides scope-aware read/write access for settings.
 *
 * In "global" scope, reads/writes go directly to the Zustand global store.
 * In "video" scope, reads come from the resolved (merged) config and
 * writes go to the per-video overrides via VideoConfigContext.
 *
 * Each tab uses this hook so the same UI works for both scopes.
 */

import { useCallback } from "react";
import { useShallow } from "zustand/react/shallow";
import { useGlobalSettingsStore } from "@/stores/useGlobalSettingsStore";
import { useVideoConfigOptional } from "@/contexts/VideoConfigContext";
import type {
    GlobalSettings,
    NoteContextMode,
    DictionaryInteractionMode,
    ViewMode,
} from "@/stores/types";

export type SettingsScope = "global" | "video";

/**
 * Returns whether the "This Video" scope is available
 * (true when inside a VideoConfigProvider, i.e. on a video page).
 */
export function useHasVideoScope(): boolean {
    const ctx = useVideoConfigOptional();
    return ctx !== null;
}

/**
 * Returns the override count (for badge display) when in video scope.
 */
export function useOverrideCount(): number {
    const ctx = useVideoConfigOptional();
    return ctx?.overrideCount ?? 0;
}

// ─── Scope-Aware Settings Hook ───────────────────────────────────────────────

export interface ScopedSettings {
    // Read
    values: GlobalSettings;

    // Field-level override info (only meaningful in video scope)
    isOverridden: (path: string) => boolean;

    // Write — these route to global store or per-video overrides
    setField: (path: string, value: unknown) => void;
    clearField: (path: string) => void;
    clearAllOverrides: () => Promise<void>;

    // Convenience writers (type-safe wrappers around setField)
    setOriginalLanguage: (lang: string) => void;
    setTranslatedLanguage: (lang: string) => void;
    setLearnerProfile: (profile: string) => void;
    setAutoPauseOnLeave: (v: boolean) => void;
    setAutoResumeOnReturn: (v: boolean) => void;
    setAutoSwitchSubtitlesOnLeave: (v: boolean) => void;
    setAutoSwitchVoiceoverOnLeave: (v: boolean) => void;
    setVoiceoverAutoSwitchThresholdMs: (ms: number) => void;
    setSummaryThresholdSeconds: (s: number) => void;
    setSubtitleContextWindowSeconds: (s: number) => void;
    setSubtitleRepeatCount: (c: number) => void;
    setSubtitleFontSize: (size: number) => void;
    setSubtitleBottomOffset: (offset: number) => void;
    toggleHideSidebars: () => void;
    setViewMode: (mode: ViewMode) => void;
    setBrowserNotificationsEnabled: (v: boolean) => void;
    setToastNotificationsEnabled: (v: boolean) => void;
    setTitleFlashEnabled: (v: boolean) => void;
    toggleLive2d: () => void;
    setLive2dModelPath: (path: string) => void;
    setLive2dModelPosition: (pos: { x: number; y: number }) => void;
    setLive2dModelScale: (scale: number) => void;
    toggleLive2dSyncWithVideo: () => void;
    setNoteContextMode: (mode: NoteContextMode) => void;
    setAILlmModel: (model: string | null) => void;
    setAITtsModel: (model: string | null) => void;
    setAILlmTaskModel: (taskKey: string, model: string | null) => void;
    setAITtsTaskModel: (taskKey: string, model: string | null) => void;
    setAIPrompt: (funcId: string, implId: string) => void;
    resetAIPrompt: (funcId: string) => void;
    setDictionaryEnabled: (v: boolean) => void;
    setDictionaryInteractionMode: (mode: DictionaryInteractionMode) => void;
}

export function useSettingsScope(scope: SettingsScope): ScopedSettings {
    const videoCtx = useVideoConfigOptional();

    // Global store read (always needed for global scope fallback)
    const globalValues = useGlobalSettingsStore(
        useShallow((s) => ({
            playback: s.playback,
            language: s.language,
            hideSidebars: s.hideSidebars,
            viewMode: s.viewMode,
            subtitleDisplay: s.subtitleDisplay,
            notifications: s.notifications,
            live2d: s.live2d,
            learnerProfile: s.learnerProfile,
            note: s.note,
            ai: s.ai,
            dictionary: s.dictionary,
        }))
    );

    // Global store actions
    const globalActions = useGlobalSettingsStore(
        useShallow((s) => ({
            setOriginalLanguage: s.setOriginalLanguage,
            setTranslatedLanguage: s.setTranslatedLanguage,
            setLearnerProfile: s.setLearnerProfile,
            setAutoPauseOnLeave: s.setAutoPauseOnLeave,
            setAutoResumeOnReturn: s.setAutoResumeOnReturn,
            setAutoSwitchSubtitlesOnLeave: s.setAutoSwitchSubtitlesOnLeave,
            setAutoSwitchVoiceoverOnLeave: s.setAutoSwitchVoiceoverOnLeave,
            setVoiceoverAutoSwitchThresholdMs: s.setVoiceoverAutoSwitchThresholdMs,
            setSummaryThresholdSeconds: s.setSummaryThresholdSeconds,
            setSubtitleContextWindowSeconds: s.setSubtitleContextWindowSeconds,
            setSubtitleRepeatCount: s.setSubtitleRepeatCount,
            setSubtitleFontSize: s.setSubtitleFontSize,
            setSubtitleBottomOffset: s.setSubtitleBottomOffset,
            toggleHideSidebars: s.toggleHideSidebars,
            setViewMode: s.setViewMode,
            setBrowserNotificationsEnabled: s.setBrowserNotificationsEnabled,
            setToastNotificationsEnabled: s.setToastNotificationsEnabled,
            setTitleFlashEnabled: s.setTitleFlashEnabled,
            toggleLive2d: s.toggleLive2d,
            setLive2dModelPath: s.setLive2dModelPath,
            setLive2dModelPosition: s.setLive2dModelPosition,
            setLive2dModelScale: s.setLive2dModelScale,
            toggleLive2dSyncWithVideo: s.toggleLive2dSyncWithVideo,
            setNoteContextMode: s.setNoteContextMode,
            setAILlmModel: s.setAILlmModel,
            setAITtsModel: s.setAITtsModel,
            setAILlmTaskModel: s.setAILlmTaskModel,
            setAITtsTaskModel: s.setAITtsTaskModel,
            setAIPrompt: s.setAIPrompt,
            resetAIPrompt: s.resetAIPrompt,
            setDictionaryEnabled: s.setDictionaryEnabled,
            setDictionaryInteractionMode: s.setDictionaryInteractionMode,
        }))
    );

    const isVideoScope = scope === "video" && videoCtx !== null;

    // Values: resolved (merged) for video scope, global for global scope
    const values: GlobalSettings = isVideoScope ? videoCtx.resolved : globalValues;

    // Override check
    const isOverridden = useCallback(
        (path: string) => {
            if (!isVideoScope) return false;
            return videoCtx.isOverridden(path);
        },
        [isVideoScope, videoCtx],
    );

    // Field setters — route to per-video context or global store
    const setField = useCallback(
        (path: string, value: unknown) => {
            if (isVideoScope) {
                videoCtx.setField(path, value);
            }
            // In global scope, setField is unused (we use typed setters)
        },
        [isVideoScope, videoCtx],
    );

    const clearField = useCallback(
        (path: string) => {
            if (isVideoScope) {
                videoCtx.clearField(path);
            }
        },
        [isVideoScope, videoCtx],
    );

    const clearAllOverrides = useCallback(async () => {
        if (isVideoScope) {
            await videoCtx.clearAll();
        }
    }, [isVideoScope, videoCtx]);

    // ─── Convenience typed setters ───────────────────────────────────────────

    const makeToggle = useCallback(
        (path: string, globalToggle: () => void) => {
            return () => {
                if (isVideoScope) {
                    // Read current resolved value, flip it, write to per-video
                    const parts = path.split(".");
                    let current: unknown = values;
                    for (const p of parts) {
                        current = (current as Record<string, unknown>)?.[p];
                    }
                    videoCtx.setField(path, !current);
                } else {
                    globalToggle();
                }
            };
        },
        [isVideoScope, videoCtx, values],
    );

    const makeSetter = useCallback(
        <T,>(path: string, globalSetter: (v: T) => void) => {
            return (v: T) => {
                if (isVideoScope) {
                    videoCtx.setField(path, v);
                } else {
                    globalSetter(v);
                }
            };
        },
        [isVideoScope, videoCtx],
    );

    return {
        values,
        isOverridden,
        setField,
        clearField,
        clearAllOverrides,

        // Language
        setOriginalLanguage: makeSetter("language.original", globalActions.setOriginalLanguage),
        setTranslatedLanguage: makeSetter("language.translated", globalActions.setTranslatedLanguage),

        // Profile
        setLearnerProfile: makeSetter("learnerProfile", globalActions.setLearnerProfile),

        // Playback
        setAutoPauseOnLeave: makeSetter("playback.autoPauseOnLeave", globalActions.setAutoPauseOnLeave),
        setAutoResumeOnReturn: makeSetter("playback.autoResumeOnReturn", globalActions.setAutoResumeOnReturn),
        setAutoSwitchSubtitlesOnLeave: makeSetter("playback.autoSwitchSubtitlesOnLeave", globalActions.setAutoSwitchSubtitlesOnLeave),
        setAutoSwitchVoiceoverOnLeave: makeSetter("playback.autoSwitchVoiceoverOnLeave", globalActions.setAutoSwitchVoiceoverOnLeave),
        setVoiceoverAutoSwitchThresholdMs: makeSetter("playback.voiceoverAutoSwitchThresholdMs", globalActions.setVoiceoverAutoSwitchThresholdMs),
        setSummaryThresholdSeconds: makeSetter("playback.summaryThresholdSeconds", globalActions.setSummaryThresholdSeconds),
        setSubtitleContextWindowSeconds: makeSetter("playback.subtitleContextWindowSeconds", globalActions.setSubtitleContextWindowSeconds),
        setSubtitleRepeatCount: makeSetter("playback.subtitleRepeatCount", globalActions.setSubtitleRepeatCount),

        // Subtitle display
        setSubtitleFontSize: makeSetter("subtitleDisplay.fontSize", globalActions.setSubtitleFontSize),
        setSubtitleBottomOffset: makeSetter("subtitleDisplay.bottomOffset", globalActions.setSubtitleBottomOffset),

        // View
        toggleHideSidebars: makeToggle("hideSidebars", globalActions.toggleHideSidebars),
        setViewMode: makeSetter("viewMode", globalActions.setViewMode),

        // Notifications
        setBrowserNotificationsEnabled: makeSetter("notifications.browserNotificationsEnabled", globalActions.setBrowserNotificationsEnabled),
        setToastNotificationsEnabled: makeSetter("notifications.toastNotificationsEnabled", globalActions.setToastNotificationsEnabled),
        setTitleFlashEnabled: makeSetter("notifications.titleFlashEnabled", globalActions.setTitleFlashEnabled),

        // Live2D
        toggleLive2d: makeToggle("live2d.enabled", globalActions.toggleLive2d),
        setLive2dModelPath: makeSetter("live2d.modelPath", globalActions.setLive2dModelPath),
        setLive2dModelPosition: makeSetter("live2d.modelPosition", globalActions.setLive2dModelPosition),
        setLive2dModelScale: makeSetter("live2d.modelScale", globalActions.setLive2dModelScale),
        toggleLive2dSyncWithVideo: makeToggle("live2d.syncWithVideoAudio", globalActions.toggleLive2dSyncWithVideo),

        // Note
        setNoteContextMode: makeSetter("note.contextMode", globalActions.setNoteContextMode),

        // AI
        setAILlmModel: makeSetter("ai.llmModel", globalActions.setAILlmModel),
        setAITtsModel: makeSetter("ai.ttsModel", globalActions.setAITtsModel),
        setAILlmTaskModel: useCallback(
            (taskKey: string, model: string | null) => {
                if (isVideoScope) {
                    const path = `ai.llmTaskModels.${taskKey}`;
                    if (model) {
                        videoCtx.setField(path, model);
                    } else {
                        videoCtx.clearField(path);
                    }
                } else {
                    globalActions.setAILlmTaskModel(taskKey, model);
                }
            },
            [isVideoScope, videoCtx, globalActions],
        ),
        setAITtsTaskModel: useCallback(
            (taskKey: string, model: string | null) => {
                if (isVideoScope) {
                    const path = `ai.ttsTaskModels.${taskKey}`;
                    if (model) {
                        videoCtx.setField(path, model);
                    } else {
                        videoCtx.clearField(path);
                    }
                } else {
                    globalActions.setAITtsTaskModel(taskKey, model);
                }
            },
            [isVideoScope, videoCtx, globalActions],
        ),
        setAIPrompt: useCallback(
            (funcId: string, implId: string) => {
                if (isVideoScope) {
                    // For prompts, we merge at the key level
                    const currentPrompts = values.ai.prompts;
                    videoCtx.setField("ai.prompts", { ...currentPrompts, [funcId]: implId });
                } else {
                    globalActions.setAIPrompt(funcId, implId);
                }
            },
            [isVideoScope, videoCtx, values.ai.prompts, globalActions],
        ),
        resetAIPrompt: useCallback(
            (funcId: string) => {
                if (isVideoScope) {
                    // Remove this prompt key from overrides
                    const currentOverridePrompts = (videoCtx.overrides.ai as Record<string, unknown> | undefined)?.prompts;
                    if (currentOverridePrompts && typeof currentOverridePrompts === "object") {
                        const { [funcId]: _, ...rest } = currentOverridePrompts as Record<string, string>;
                        if (Object.keys(rest).length === 0) {
                            videoCtx.clearField("ai.prompts");
                        } else {
                            videoCtx.setField("ai.prompts", rest);
                        }
                    }
                } else {
                    globalActions.resetAIPrompt(funcId);
                }
            },
            [isVideoScope, videoCtx, globalActions],
        ),

        // Dictionary
        setDictionaryEnabled: makeSetter("dictionary.enabled", globalActions.setDictionaryEnabled),
        setDictionaryInteractionMode: makeSetter("dictionary.interactionMode", globalActions.setDictionaryInteractionMode),
    };
}

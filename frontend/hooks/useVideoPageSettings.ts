"use client";

import { useCallback } from "react";
import { useShallow } from "zustand/react/shallow";
import { useGlobalSettingsStore } from "@/stores";
import { useVideoConfigOptional } from "@/contexts/VideoConfigContext";

/**
 * Optimized hook for video page settings.
 * Uses shallow equality to prevent unnecessary re-renders.
 */
export function useVideoPageSettings() {
    const videoCtx = useVideoConfigOptional();

    // Single shallow selector for all settings - prevents 25+ individual subscriptions
    const globalSettings = useGlobalSettingsStore(
        useShallow((s) => ({
            playback: s.playback,
            language: s.language,
            hideSidebars: s.hideSidebars,
            viewMode: s.viewMode,
            subtitleDisplay: s.subtitleDisplay,
            live2d: s.live2d,
        }))
    );
    const settings = videoCtx?.resolved ?? globalSettings;

    // Derived values for convenience
    const derived = {
        autoPauseOnLeave: settings.playback.autoPauseOnLeave,
        autoResumeOnReturn: settings.playback.autoResumeOnReturn,
        autoSwitchSubtitlesOnLeave: settings.playback.autoSwitchSubtitlesOnLeave,
        summaryThresholdSeconds: settings.playback.summaryThresholdSeconds,
        subtitleContextWindowSeconds: settings.playback.subtitleContextWindowSeconds,
        subtitleRepeatCount: settings.playback.subtitleRepeatCount,
        subtitleFontSize: settings.subtitleDisplay.fontSize,
        subtitleBottomOffset: settings.subtitleDisplay.bottomOffset,
        originalLanguage: settings.language.original,
        // Target language for all AI outputs (translations, explanations, timelines, notes)
        targetLanguage: settings.language.translated,
        live2dEnabled: settings.live2d.enabled,
        live2dModelPath: settings.live2d.modelPath,
        live2dModelPosition: settings.live2d.modelPosition,
        live2dModelScale: settings.live2d.modelScale,
        live2dSyncWithVideoAudio: settings.live2d.syncWithVideoAudio,
        hideSidebars: settings.hideSidebars,
    };

    // Single shallow selector for all actions
    const actions = useGlobalSettingsStore(
        useShallow((s) => ({
            setAutoPauseOnLeave: s.setAutoPauseOnLeave,
            setAutoResumeOnReturn: s.setAutoResumeOnReturn,
            setAutoSwitchSubtitlesOnLeave: s.setAutoSwitchSubtitlesOnLeave,
            setSummaryThresholdSeconds: s.setSummaryThresholdSeconds,
            setSubtitleContextWindowSeconds: s.setSubtitleContextWindowSeconds,
            setSubtitleRepeatCount: s.setSubtitleRepeatCount,
            setSubtitleFontSize: s.setSubtitleFontSize,
            setSubtitleBottomOffset: s.setSubtitleBottomOffset,
            toggleHideSidebars: s.toggleHideSidebars,
            setViewMode: s.setViewMode,
            setOriginalLanguage: s.setOriginalLanguage,
            setTargetLanguage: s.setTranslatedLanguage,
            toggleLive2d: s.toggleLive2d,
            setLive2dModelPath: s.setLive2dModelPath,
            setLive2dModelPosition: s.setLive2dModelPosition,
            setLive2dModelScale: s.setLive2dModelScale,
            toggleLive2dSyncWithVideo: s.toggleLive2dSyncWithVideo,
        }))
    );

    // Toggle helpers (memoized)
    const toggleAutoPause = useCallback(() => {
        actions.setAutoPauseOnLeave(!derived.autoPauseOnLeave);
    }, [actions, derived.autoPauseOnLeave]);

    const toggleAutoResume = useCallback(() => {
        actions.setAutoResumeOnReturn(!derived.autoResumeOnReturn);
    }, [actions, derived.autoResumeOnReturn]);

    return {
        settings,
        derived,
        actions,
        toggleAutoPause,
        toggleAutoResume,
    };
}

/**
 * Optimized hook for notification settings.
 */
export function useNotificationSettingsOptimized() {
    return useGlobalSettingsStore(
        useShallow((s) => ({
            browserNotificationsEnabled: s.notifications.browserNotificationsEnabled,
            toastNotificationsEnabled: s.notifications.toastNotificationsEnabled,
            titleFlashEnabled: s.notifications.titleFlashEnabled,
            setBrowserNotificationsEnabled: s.setBrowserNotificationsEnabled,
            setToastNotificationsEnabled: s.setToastNotificationsEnabled,
            setTitleFlashEnabled: s.setTitleFlashEnabled,
        }))
    );
}

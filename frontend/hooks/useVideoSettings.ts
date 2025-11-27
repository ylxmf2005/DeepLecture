"use client";

import { useCallback, useEffect } from "react";
import { useGlobalSettingsStore } from "@/stores";

/**
 * useVideoSettings - Compatibility wrapper around useGlobalSettingsStore
 *
 * This hook provides the same API as before but delegates to the zustand store.
 * All settings are persisted via the store's persist middleware (localStorage).
 * Language settings are loaded from server config on mount (read-only).
 */

export interface VideoSettings {
    autoPauseOnLeave: boolean;
    autoResumeOnReturn: boolean;
    summaryThresholdSeconds: number;
    subtitleContextWindowSeconds: number;
    subtitleRepeatCount: number;
    subtitleFontSize: number;
    subtitleBottomOffset: number;
    hideSidebars: boolean;
    originalLanguage: string;
    aiLanguage: string;
    translatedLanguage: string;
    languagesLoading: boolean;
    live2dEnabled: boolean;
    live2dModelPath: string;
    live2dModelPosition: { x: number; y: number };
    live2dModelScale: number;
    live2dSyncWithVideoAudio: boolean;
}

export interface VideoSettingsActions {
    setAutoPauseOnLeave: (value: boolean) => void;
    toggleAutoPause: () => void;
    setAutoResumeOnReturn: (value: boolean) => void;
    toggleAutoResume: () => void;
    setSummaryThresholdSeconds: (seconds: number) => void;
    setSubtitleContextWindowSeconds: (seconds: number) => void;
    setSubtitleRepeatCount: (value: number) => void;
    setSubtitleFontSize: (size: number) => void;
    setSubtitleBottomOffset: (offset: number) => void;
    toggleHideSidebars: () => void;
    setOriginalLanguage: (value: string) => void;
    setAiLanguage: (value: string) => void;
    setTranslatedLanguage: (value: string) => void;
    toggleLive2d: () => void;
    setLive2dModelPath: (path: string) => void;
    setLive2dModelPosition: (position: { x: number; y: number }) => void;
    setLive2dModelScale: (scale: number) => void;
    toggleLive2dSyncWithVideo: () => void;
}

export interface UseVideoSettingsReturn extends VideoSettings, VideoSettingsActions {}

export function useVideoSettings(): UseVideoSettingsReturn {
    // Get state from store - use individual selectors to avoid object creation
    const playback = useGlobalSettingsStore((s) => s.playback);
    const language = useGlobalSettingsStore((s) => s.language);
    const hideSidebars = useGlobalSettingsStore((s) => s.hideSidebars);
    const subtitleDisplay = useGlobalSettingsStore((s) => s.subtitleDisplay);
    const live2d = useGlobalSettingsStore((s) => s.live2d);
    const _languageLoading = useGlobalSettingsStore((s) => s._languageLoading);

    // Get actions from store - individual selectors
    const setAutoPauseOnLeave = useGlobalSettingsStore((s) => s.setAutoPauseOnLeave);
    const setAutoResumeOnReturn = useGlobalSettingsStore((s) => s.setAutoResumeOnReturn);
    const setSummaryThresholdSeconds = useGlobalSettingsStore((s) => s.setSummaryThresholdSeconds);
    const setSubtitleContextWindowSeconds = useGlobalSettingsStore((s) => s.setSubtitleContextWindowSeconds);
    const setSubtitleRepeatCount = useGlobalSettingsStore((s) => s.setSubtitleRepeatCount);
    const setSubtitleFontSize = useGlobalSettingsStore((s) => s.setSubtitleFontSize);
    const setSubtitleBottomOffset = useGlobalSettingsStore((s) => s.setSubtitleBottomOffset);
    const toggleHideSidebars = useGlobalSettingsStore((s) => s.toggleHideSidebars);
    const setOriginalLanguage = useGlobalSettingsStore((s) => s.setOriginalLanguage);
    const setAiLanguage = useGlobalSettingsStore((s) => s.setAiLanguage);
    const setTranslatedLanguage = useGlobalSettingsStore((s) => s.setTranslatedLanguage);
    const loadLanguageFromServer = useGlobalSettingsStore((s) => s.loadLanguageFromServer);
    const toggleLive2d = useGlobalSettingsStore((s) => s.toggleLive2d);
    const setLive2dModelPath = useGlobalSettingsStore((s) => s.setLive2dModelPath);
    const setLive2dModelPosition = useGlobalSettingsStore((s) => s.setLive2dModelPosition);
    const setLive2dModelScale = useGlobalSettingsStore((s) => s.setLive2dModelScale);
    const toggleLive2dSyncWithVideo = useGlobalSettingsStore((s) => s.toggleLive2dSyncWithVideo);

    // Load language settings from server on mount
    useEffect(() => {
        loadLanguageFromServer();
    }, [loadLanguageFromServer]);

    const toggleAutoPause = useCallback(() => {
        setAutoPauseOnLeave(!playback.autoPauseOnLeave);
    }, [setAutoPauseOnLeave, playback.autoPauseOnLeave]);

    const toggleAutoResume = useCallback(() => {
        setAutoResumeOnReturn(!playback.autoResumeOnReturn);
    }, [setAutoResumeOnReturn, playback.autoResumeOnReturn]);

    return {
        autoPauseOnLeave: playback.autoPauseOnLeave,
        autoResumeOnReturn: playback.autoResumeOnReturn,
        summaryThresholdSeconds: playback.summaryThresholdSeconds,
        subtitleContextWindowSeconds: playback.subtitleContextWindowSeconds,
        subtitleRepeatCount: playback.subtitleRepeatCount,
        subtitleFontSize: subtitleDisplay.fontSize,
        subtitleBottomOffset: subtitleDisplay.bottomOffset,
        hideSidebars,
        originalLanguage: language.original,
        aiLanguage: language.ai,
        translatedLanguage: language.translated,
        languagesLoading: _languageLoading,
        live2dEnabled: live2d.enabled,
        live2dModelPath: live2d.modelPath,
        live2dModelPosition: live2d.modelPosition,
        live2dModelScale: live2d.modelScale,
        live2dSyncWithVideoAudio: live2d.syncWithVideoAudio,
        setAutoPauseOnLeave,
        toggleAutoPause,
        setAutoResumeOnReturn,
        toggleAutoResume,
        setSummaryThresholdSeconds,
        setSubtitleContextWindowSeconds,
        setSubtitleRepeatCount,
        setSubtitleFontSize,
        setSubtitleBottomOffset,
        toggleHideSidebars,
        setOriginalLanguage,
        setAiLanguage,
        setTranslatedLanguage,
        toggleLive2d,
        setLive2dModelPath,
        setLive2dModelPosition,
        setLive2dModelScale,
        toggleLive2dSyncWithVideo,
    };
}

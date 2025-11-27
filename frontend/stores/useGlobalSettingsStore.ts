"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import {
    GlobalSettings,
    GlobalSettingsActions,
    DEFAULT_GLOBAL_SETTINGS,
    STORAGE_KEYS,
    STORAGE_VERSIONS,
} from "./types";
import { getLanguageSettings } from "@/lib/api";

interface GlobalSettingsState extends GlobalSettings {
    _hydrated: boolean;
    _languageLoading: boolean;
}

type GlobalSettingsStore = GlobalSettingsState & GlobalSettingsActions;

export const useGlobalSettingsStore = create<GlobalSettingsStore>()(
    persist(
        (set, get) => ({
            ...DEFAULT_GLOBAL_SETTINGS,
            _hydrated: false,
            _languageLoading: false,

            setAutoPauseOnLeave: (value) =>
                set((state) => ({
                    playback: { ...state.playback, autoPauseOnLeave: value },
                })),

            setAutoResumeOnReturn: (value) =>
                set((state) => ({
                    playback: { ...state.playback, autoResumeOnReturn: value },
                })),

            setSummaryThresholdSeconds: (seconds) =>
                set((state) => ({
                    playback: { ...state.playback, summaryThresholdSeconds: seconds },
                })),

            setSubtitleContextWindowSeconds: (seconds) =>
                set((state) => ({
                    playback: { ...state.playback, subtitleContextWindowSeconds: seconds },
                })),

            setSubtitleRepeatCount: (count) =>
                set((state) => ({
                    playback: { ...state.playback, subtitleRepeatCount: count },
                })),

            setSubtitleFontSize: (size) =>
                set((state) => ({
                    subtitleDisplay: {
                        ...state.subtitleDisplay,
                        // Clamp to a sane range to avoid ridiculous values
                        fontSize: Math.min(Math.max(size, 10), 72),
                    },
                })),

            setSubtitleBottomOffset: (offset) =>
                set((state) => ({
                    subtitleDisplay: {
                        ...state.subtitleDisplay,
                        // Allow a reasonable vertical range
                        bottomOffset: Math.min(Math.max(offset, 0), 200),
                    },
                })),

            setOriginalLanguage: (lang) =>
                set((state) => ({
                    language: { ...state.language, original: lang },
                })),

            setAiLanguage: (lang) =>
                set((state) => ({
                    language: { ...state.language, ai: lang },
                })),

            setTranslatedLanguage: (lang) =>
                set((state) => ({
                    language: { ...state.language, translated: lang },
                })),

            loadLanguageFromServer: async () => {
                set({ _languageLoading: true });
                try {
                    const data = await getLanguageSettings();
                    set((state) => ({
                        language: {
                            original: data.original_language ?? state.language.original,
                            ai: data.ai_language ?? state.language.ai,
                            translated: data.translated_language ?? state.language.translated,
                        },
                    }));
                } catch (e) {
                    console.error("Failed to load language from server:", e);
                } finally {
                    set({ _languageLoading: false });
                }
            },

            toggleHideSidebars: () =>
                set((state) => ({ hideSidebars: !state.hideSidebars })),

            toggleLive2d: () =>
                set((state) => ({
                    live2d: { ...state.live2d, enabled: !state.live2d.enabled },
                })),

            setLive2dModelPath: (path) =>
                set((state) => ({
                    live2d: { ...state.live2d, modelPath: path },
                })),

            setLive2dModelPosition: (position) =>
                set((state) => ({
                    live2d: { ...state.live2d, modelPosition: position },
                })),

            setLive2dModelScale: (scale) =>
                set((state) => ({
                    live2d: { ...state.live2d, modelScale: scale },
                })),

            toggleLive2dSyncWithVideo: () =>
                set((state) => ({
                    live2d: { ...state.live2d, syncWithVideoAudio: !state.live2d.syncWithVideoAudio },
                })),

            setLearnerProfile: (profile) => set({ learnerProfile: profile }),

            resetToDefaults: () =>
                set({
                    ...DEFAULT_GLOBAL_SETTINGS,
                    _hydrated: true,
                }),
        }),
        {
            name: STORAGE_KEYS.GLOBAL_SETTINGS,
            version: STORAGE_VERSIONS.GLOBAL_SETTINGS,
            storage: createJSONStorage(() => localStorage),

            partialize: (state) => ({
                playback: state.playback,
                language: state.language,
                subtitleDisplay: state.subtitleDisplay,
                hideSidebars: state.hideSidebars,
                live2d: state.live2d,
                learnerProfile: state.learnerProfile,
            }),

            onRehydrateStorage: () => () => {
                useGlobalSettingsStore.setState({ _hydrated: true });
            },

            migrate: (persistedState) => {
                // Merge persisted state with defaults so newly added settings
                // (like subtitleDisplay) always have sane values.
                if (!persistedState) {
                    return {
                        ...DEFAULT_GLOBAL_SETTINGS,
                        _hydrated: false,
                        _languageLoading: false,
                    };
                }

                const state = persistedState as GlobalSettingsState;

                return {
                    ...DEFAULT_GLOBAL_SETTINGS,
                    ...state,
                    playback: {
                        ...DEFAULT_GLOBAL_SETTINGS.playback,
                        ...(state.playback ?? DEFAULT_GLOBAL_SETTINGS.playback),
                    },
                    language: {
                        ...DEFAULT_GLOBAL_SETTINGS.language,
                        ...(state.language ?? DEFAULT_GLOBAL_SETTINGS.language),
                    },
                    live2d: {
                        ...DEFAULT_GLOBAL_SETTINGS.live2d,
                        ...(state.live2d ?? DEFAULT_GLOBAL_SETTINGS.live2d),
                    },
                    subtitleDisplay: {
                        ...DEFAULT_GLOBAL_SETTINGS.subtitleDisplay,
                        ...(state.subtitleDisplay ?? DEFAULT_GLOBAL_SETTINGS.subtitleDisplay),
                    },
                } as GlobalSettingsState;
            },
        }
    )
);

export const usePlaybackSettings = () =>
    useGlobalSettingsStore((state) => state.playback);

export const useLanguageSettings = () =>
    useGlobalSettingsStore((state) => state.language);

export const useLive2dSettings = () =>
    useGlobalSettingsStore((state) => state.live2d);

export const useLearnerProfile = () =>
    useGlobalSettingsStore((state) => state.learnerProfile);

export const useIsHydrated = () =>
    useGlobalSettingsStore((state) => state._hydrated);

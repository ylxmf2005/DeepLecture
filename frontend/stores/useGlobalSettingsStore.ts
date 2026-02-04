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
import { getLanguageSettings, getNoteDefaults, getAppConfig } from "@/lib/api";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";

const log = logger.scope("GlobalSettingsStore");

interface GlobalSettingsState extends GlobalSettings {
    _hydrated: boolean;
    _languageLoading: boolean;
}

type GlobalSettingsStore = GlobalSettingsState & GlobalSettingsActions;

export const useGlobalSettingsStore = create<GlobalSettingsStore>()(
    persist(
        (set) => ({
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

            setAutoSwitchSubtitlesOnLeave: (value) =>
                set((state) => ({
                    playback: { ...state.playback, autoSwitchSubtitlesOnLeave: value },
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
                            original: data.originalLanguage ?? state.language.original,
                            translated: data.translatedLanguage ?? state.language.translated,
                        },
                    }));
                } catch (e) {
                    log.error("Failed to load language from server", toError(e));
                } finally {
                    set({ _languageLoading: false });
                }
            },

            toggleHideSidebars: () =>
                set((state) => ({ hideSidebars: !state.hideSidebars })),

            setViewMode: (mode) => set({ viewMode: mode }),

            setBrowserNotificationsEnabled: (value) =>
                set((state) => ({
                    notifications: { ...state.notifications, browserNotificationsEnabled: value },
                })),

            setToastNotificationsEnabled: (value) =>
                set((state) => ({
                    notifications: { ...state.notifications, toastNotificationsEnabled: value },
                })),

            setTitleFlashEnabled: (value) =>
                set((state) => ({
                    notifications: { ...state.notifications, titleFlashEnabled: value },
                })),

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

            setNoteContextMode: (mode) =>
                set((state) => ({
                    note: { ...state.note, contextMode: mode },
                })),

            loadNoteDefaultsFromServer: async () => {
                try {
                    const data = await getNoteDefaults();
                    set((state) => ({
                        note: {
                            ...state.note,
                            contextMode: data.defaultContextMode ?? state.note.contextMode,
                        },
                    }));
                } catch (e) {
                    log.error("Failed to load note defaults from server", toError(e));
                }
            },

            setAILlmModel: (model) =>
                set((state) => ({
                    ai: { ...state.ai, llmModel: model },
                })),

            setAITtsModel: (model) =>
                set((state) => ({
                    ai: { ...state.ai, ttsModel: model },
                })),

            setAIPrompt: (funcId, implId) =>
                set((state) => ({
                    ai: {
                        ...state.ai,
                        prompts: { ...state.ai.prompts, [funcId]: implId },
                    },
                })),

            resetAIPrompt: (funcId) =>
                set((state) => {
                    const { [funcId]: _, ...rest } = state.ai.prompts;
                    return { ai: { ...state.ai, prompts: rest } };
                }),

            loadAIConfigFromServer: async () => {
                try {
                    await getAppConfig();
                    // Config loaded - defaults are managed by backend
                    // User preferences in store override backend defaults
                } catch (e) {
                    log.error("Failed to load AI config from server", toError(e));
                }
            },

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
                notifications: state.notifications,
                hideSidebars: state.hideSidebars,
                viewMode: state.viewMode,
                live2d: state.live2d,
                learnerProfile: state.learnerProfile,
                note: state.note,
                ai: state.ai,
            }),

            onRehydrateStorage: () => () => {
                useGlobalSettingsStore.setState({ _hydrated: true });
            },

            migrate: (persistedState, version) => {
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

                // v1 → v2: Remove language.ai, use it as translated if present
                // (language.ai was the AI output language, now consolidated into translated)
                let migratedLanguage = {
                    ...DEFAULT_GLOBAL_SETTINGS.language,
                    ...(state.language ?? DEFAULT_GLOBAL_SETTINGS.language),
                };

                if (version < 2 && state.language) {
                    const legacyLang = state.language as { original?: string; ai?: string; translated?: string };
                    // If user had ai language set, use it as translated (AI outputs should use this)
                    if (legacyLang.ai) {
                        migratedLanguage = {
                            original: legacyLang.original ?? DEFAULT_GLOBAL_SETTINGS.language.original,
                            translated: legacyLang.ai, // Use ai as target language
                        };
                    }
                }

                return {
                    ...DEFAULT_GLOBAL_SETTINGS,
                    ...state,
                    playback: {
                        ...DEFAULT_GLOBAL_SETTINGS.playback,
                        ...(state.playback ?? DEFAULT_GLOBAL_SETTINGS.playback),
                    },
                    language: migratedLanguage,
                    live2d: {
                        ...DEFAULT_GLOBAL_SETTINGS.live2d,
                        ...(state.live2d ?? DEFAULT_GLOBAL_SETTINGS.live2d),
                    },
                    subtitleDisplay: {
                        ...DEFAULT_GLOBAL_SETTINGS.subtitleDisplay,
                        ...(state.subtitleDisplay ?? DEFAULT_GLOBAL_SETTINGS.subtitleDisplay),
                    },
                    notifications: {
                        ...DEFAULT_GLOBAL_SETTINGS.notifications,
                        ...((state as GlobalSettingsState & { notifications?: typeof DEFAULT_GLOBAL_SETTINGS.notifications }).notifications ?? DEFAULT_GLOBAL_SETTINGS.notifications),
                    },
                    note: {
                        ...DEFAULT_GLOBAL_SETTINGS.note,
                        ...(state.note ?? DEFAULT_GLOBAL_SETTINGS.note),
                    },
                    ai: {
                        ...DEFAULT_GLOBAL_SETTINGS.ai,
                        ...(state.ai ?? DEFAULT_GLOBAL_SETTINGS.ai),
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

export const useNotificationSettings = () =>
    useGlobalSettingsStore((state) => state.notifications);

export const useLearnerProfile = () =>
    useGlobalSettingsStore((state) => state.learnerProfile);

export const useNoteSettings = () =>
    useGlobalSettingsStore((state) => state.note);

export const useIsHydrated = () =>
    useGlobalSettingsStore((state) => state._hydrated);

export const useAISettings = () =>
    useGlobalSettingsStore((state) => state.ai);

export const useViewMode = () =>
    useGlobalSettingsStore((state) => state.viewMode);

"use client";

import { create } from "zustand";
import {
    GlobalSettings,
    GlobalSettingsActions,
    DEFAULT_GLOBAL_SETTINGS,
} from "./types";
import { getLanguageSettings, getNoteDefaults, getAppConfig, getGlobalConfig, putGlobalConfig } from "@/lib/api";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";

const log = logger.scope("GlobalSettingsStore");

interface GlobalSettingsState extends GlobalSettings {
    _hydrated: boolean;
    _languageLoading: boolean;
}

type GlobalSettingsStore = GlobalSettingsState & GlobalSettingsActions;

let saveTimer: ReturnType<typeof setTimeout> | null = null;

function scheduleSync() {
    if (typeof window === "undefined") return;
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(async () => {
        try {
            const state = useGlobalSettingsStore.getState();
            const payload: Partial<GlobalSettings> = {
                playback: state.playback,
                language: state.language,
                hideSidebars: state.hideSidebars,
                viewMode: state.viewMode,
                subtitleDisplay: state.subtitleDisplay,
                notifications: state.notifications,
                live2d: state.live2d,
                learnerProfile: state.learnerProfile,
                note: state.note,
                ai: state.ai,
                dictionary: state.dictionary,
            };
            await putGlobalConfig(payload);
        } catch (error) {
            log.warn("Failed to sync global config", { error: toError(error).message });
        }
    }, 300);
}

function patchAndSync(set: (fn: (state: GlobalSettingsState) => Partial<GlobalSettingsState>) => void, fn: (state: GlobalSettingsState) => Partial<GlobalSettingsState>) {
    set(fn);
    scheduleSync();
}

export const useGlobalSettingsStore = create<GlobalSettingsStore>()((set) => ({
    ...DEFAULT_GLOBAL_SETTINGS,
    _hydrated: false,
    _languageLoading: false,

    setAutoPauseOnLeave: (value) =>
        patchAndSync(set, (state) => ({ playback: { ...state.playback, autoPauseOnLeave: value } })),

    setAutoResumeOnReturn: (value) =>
        patchAndSync(set, (state) => ({ playback: { ...state.playback, autoResumeOnReturn: value } })),

    setAutoSwitchSubtitlesOnLeave: (value) =>
        patchAndSync(set, (state) => ({ playback: { ...state.playback, autoSwitchSubtitlesOnLeave: value } })),

    setSummaryThresholdSeconds: (seconds) =>
        patchAndSync(set, (state) => ({ playback: { ...state.playback, summaryThresholdSeconds: seconds } })),

    setSubtitleContextWindowSeconds: (seconds) =>
        patchAndSync(set, (state) => ({ playback: { ...state.playback, subtitleContextWindowSeconds: seconds } })),

    setSubtitleRepeatCount: (count) =>
        patchAndSync(set, (state) => ({ playback: { ...state.playback, subtitleRepeatCount: count } })),

    setSubtitleFontSize: (size) =>
        patchAndSync(set, (state) => ({
            subtitleDisplay: {
                ...state.subtitleDisplay,
                fontSize: Math.min(Math.max(size, 10), 72),
            },
        })),

    setSubtitleBottomOffset: (offset) =>
        patchAndSync(set, (state) => ({
            subtitleDisplay: {
                ...state.subtitleDisplay,
                bottomOffset: Math.min(Math.max(offset, 0), 200),
            },
        })),

    setOriginalLanguage: (lang) =>
        patchAndSync(set, (state) => ({ language: { ...state.language, original: lang } })),

    setTranslatedLanguage: (lang) =>
        patchAndSync(set, (state) => ({ language: { ...state.language, translated: lang } })),

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
            scheduleSync();
        } catch (e) {
            log.error("Failed to load language from server", toError(e));
        } finally {
            set({ _languageLoading: false });
        }
    },

    toggleHideSidebars: () =>
        patchAndSync(set, (state) => ({ hideSidebars: !state.hideSidebars })),

    setViewMode: (mode) => patchAndSync(set, () => ({ viewMode: mode })),

    setBrowserNotificationsEnabled: (value) =>
        patchAndSync(set, (state) => ({ notifications: { ...state.notifications, browserNotificationsEnabled: value } })),

    setToastNotificationsEnabled: (value) =>
        patchAndSync(set, (state) => ({ notifications: { ...state.notifications, toastNotificationsEnabled: value } })),

    setTitleFlashEnabled: (value) =>
        patchAndSync(set, (state) => ({ notifications: { ...state.notifications, titleFlashEnabled: value } })),

    toggleLive2d: () =>
        patchAndSync(set, (state) => ({ live2d: { ...state.live2d, enabled: !state.live2d.enabled } })),

    setLive2dModelPath: (path) =>
        patchAndSync(set, (state) => ({ live2d: { ...state.live2d, modelPath: path } })),

    setLive2dModelPosition: (position) =>
        patchAndSync(set, (state) => ({ live2d: { ...state.live2d, modelPosition: position } })),

    setLive2dModelScale: (scale) =>
        patchAndSync(set, (state) => ({ live2d: { ...state.live2d, modelScale: scale } })),

    toggleLive2dSyncWithVideo: () =>
        patchAndSync(set, (state) => ({ live2d: { ...state.live2d, syncWithVideoAudio: !state.live2d.syncWithVideoAudio } })),

    setLearnerProfile: (profile) => patchAndSync(set, () => ({ learnerProfile: profile })),

    setNoteContextMode: (mode) =>
        patchAndSync(set, (state) => ({ note: { ...state.note, contextMode: mode } })),

    loadNoteDefaultsFromServer: async () => {
        try {
            const data = await getNoteDefaults();
            set((state) => ({
                note: {
                    ...state.note,
                    contextMode: data.defaultContextMode ?? state.note.contextMode,
                },
            }));
            scheduleSync();
        } catch (e) {
            log.error("Failed to load note defaults from server", toError(e));
        }
    },

    setAILlmModel: (model) =>
        patchAndSync(set, (state) => ({ ai: { ...state.ai, llmModel: model } })),

    setAITtsModel: (model) =>
        patchAndSync(set, (state) => ({ ai: { ...state.ai, ttsModel: model } })),

    setAIPrompt: (funcId, implId) =>
        patchAndSync(set, (state) => ({ ai: { ...state.ai, prompts: { ...state.ai.prompts, [funcId]: implId } } })),

    resetAIPrompt: (funcId) =>
        patchAndSync(set, (state) => {
            const { [funcId]: _, ...rest } = state.ai.prompts;
            return { ai: { ...state.ai, prompts: rest } };
        }),

    loadAIConfigFromServer: async () => {
        try {
            await getAppConfig();
        } catch (e) {
            log.error("Failed to load AI config from server", toError(e));
        }
    },

    setDictionaryEnabled: (value) =>
        patchAndSync(set, (state) => ({ dictionary: { ...state.dictionary, enabled: value } })),

    setDictionaryInteractionMode: (mode) =>
        patchAndSync(set, (state) => ({ dictionary: { ...state.dictionary, interactionMode: mode } })),

    resetToDefaults: () => {
        set({ ...DEFAULT_GLOBAL_SETTINGS, _hydrated: true });
        scheduleSync();
    },
}));

if (typeof window !== "undefined") {
    void (async () => {
        try {
            const remote = await getGlobalConfig();
            useGlobalSettingsStore.setState((state) => ({
                ...state,
                ...DEFAULT_GLOBAL_SETTINGS,
                ...remote,
                playback: { ...DEFAULT_GLOBAL_SETTINGS.playback, ...(remote.playback ?? state.playback) },
                language: { ...DEFAULT_GLOBAL_SETTINGS.language, ...(remote.language ?? state.language) },
                subtitleDisplay: { ...DEFAULT_GLOBAL_SETTINGS.subtitleDisplay, ...(remote.subtitleDisplay ?? state.subtitleDisplay) },
                notifications: { ...DEFAULT_GLOBAL_SETTINGS.notifications, ...(remote.notifications ?? state.notifications) },
                live2d: { ...DEFAULT_GLOBAL_SETTINGS.live2d, ...(remote.live2d ?? state.live2d) },
                note: { ...DEFAULT_GLOBAL_SETTINGS.note, ...(remote.note ?? state.note) },
                ai: { ...DEFAULT_GLOBAL_SETTINGS.ai, ...(remote.ai ?? state.ai) },
                dictionary: { ...DEFAULT_GLOBAL_SETTINGS.dictionary, ...(remote.dictionary ?? state.dictionary) },
                _hydrated: true,
            }));

            localStorage.removeItem("courseSubtitle:global-settings");
        } catch (error) {
            log.warn("Failed to load global config from backend", { error: toError(error).message });
            useGlobalSettingsStore.setState({ _hydrated: true });
        }
    })();
}

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

export const useDictionarySettings = () =>
    useGlobalSettingsStore((state) => state.dictionary);

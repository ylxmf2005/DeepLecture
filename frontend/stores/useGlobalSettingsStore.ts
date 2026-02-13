"use client";

import { create } from "zustand";
import {
    DeepPartial,
    GlobalSettings,
    GlobalSettingsActions,
    DEFAULT_GLOBAL_SETTINGS,
} from "./types";
import { getNoteDefaults, getAppConfig, getGlobalConfig, putGlobalConfig, deleteGlobalConfig } from "@/lib/api";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";
import { useVideoConfigOptional } from "@/contexts/VideoConfigContext";

const log = logger.scope("GlobalSettingsStore");

interface GlobalSettingsState extends GlobalSettings {
    _hydrated: boolean;
    _languageLoading: boolean;
}

type GlobalSettingsStore = GlobalSettingsState & GlobalSettingsActions;

function normalizeTaskModelMap(
    value: Record<string, string | null> | undefined,
): Record<string, string | null> {
    if (!value) return {};

    const normalized: Record<string, string | null> = {};
    for (const [taskKey, model] of Object.entries(value)) {
        if (model === null) {
            normalized[taskKey] = null;
            continue;
        }
        if (typeof model !== "string") continue;
        const trimmed = model.trim();
        normalized[taskKey] = trimmed.length > 0 ? trimmed : null;
    }

    return normalized;
}

function mergeSettings(
    patch: DeepPartial<GlobalSettings>,
    previous?: GlobalSettings,
): GlobalSettings {
    const base = previous ?? DEFAULT_GLOBAL_SETTINGS;

    return {
        ...base,
        ...patch,
        playback: {
            ...base.playback,
            ...(patch.playback ?? {}),
        },
        language: {
            ...base.language,
            ...(patch.language ?? {}),
        },
        subtitleDisplay: {
            ...base.subtitleDisplay,
            ...(patch.subtitleDisplay ?? {}),
        },
        notifications: {
            ...base.notifications,
            ...(patch.notifications ?? {}),
        },
        live2d: {
            ...base.live2d,
            ...(patch.live2d ?? {}),
            modelPosition: {
                ...base.live2d.modelPosition,
                ...(patch.live2d?.modelPosition ?? {}),
            },
        },
        note: {
            ...base.note,
            ...(patch.note ?? {}),
        },
        ai: {
            ...base.ai,
            ...(patch.ai ?? {}),
            prompts: {
                ...base.ai.prompts,
                ...(patch.ai?.prompts ?? {}),
            },
            llmTaskModels: normalizeTaskModelMap(
                patch.ai?.llmTaskModels ?? base.ai.llmTaskModels,
            ),
            ttsTaskModels: normalizeTaskModelMap(
                patch.ai?.ttsTaskModels ?? base.ai.ttsTaskModels,
            ),
        },
        dictionary: {
            ...base.dictionary,
            ...(patch.dictionary ?? {}),
        },
    };
}

async function persistGlobalConfig(patch: DeepPartial<GlobalSettings>): Promise<void> {
    const hasData = Object.keys(patch).length > 0;
    if (!hasData) {
        await deleteGlobalConfig();
        return;
    }

    await putGlobalConfig(patch);
}

export const useGlobalSettingsStore = create<GlobalSettingsStore>()(
    (set, get) => ({
        ...DEFAULT_GLOBAL_SETTINGS,
        _hydrated: false,
        _languageLoading: false,

        setAutoPauseOnLeave: (value) => {
            const nextPlayback = { ...get().playback, autoPauseOnLeave: value };
            set({ playback: nextPlayback });
            putGlobalConfig({ playback: nextPlayback }).catch((e) => {
                log.error("Failed to save playback.autoPauseOnLeave", toError(e));
            });
        },

        setAutoResumeOnReturn: (value) => {
            const nextPlayback = { ...get().playback, autoResumeOnReturn: value };
            set({ playback: nextPlayback });
            putGlobalConfig({ playback: nextPlayback }).catch((e) => {
                log.error("Failed to save playback.autoResumeOnReturn", toError(e));
            });
        },

        setAutoSwitchSubtitlesOnLeave: (value) => {
            const nextPlayback = { ...get().playback, autoSwitchSubtitlesOnLeave: value };
            set({ playback: nextPlayback });
            putGlobalConfig({ playback: nextPlayback }).catch((e) => {
                log.error("Failed to save playback.autoSwitchSubtitlesOnLeave", toError(e));
            });
        },

        setAutoSwitchVoiceoverOnLeave: (value) => {
            const nextPlayback = { ...get().playback, autoSwitchVoiceoverOnLeave: value };
            set({ playback: nextPlayback });
            putGlobalConfig({ playback: nextPlayback }).catch((e) => {
                log.error("Failed to save playback.autoSwitchVoiceoverOnLeave", toError(e));
            });
        },

        setVoiceoverAutoSwitchThresholdMs: (ms) => {
            const nextPlayback = {
                ...get().playback,
                voiceoverAutoSwitchThresholdMs: Math.max(0, Math.min(ms, 10000)),
            };
            set({ playback: nextPlayback });
            putGlobalConfig({ playback: nextPlayback }).catch((e) => {
                log.error("Failed to save playback.voiceoverAutoSwitchThresholdMs", toError(e));
            });
        },

        setSummaryThresholdSeconds: (seconds) => {
            const nextPlayback = { ...get().playback, summaryThresholdSeconds: seconds };
            set({ playback: nextPlayback });
            putGlobalConfig({ playback: nextPlayback }).catch((e) => {
                log.error("Failed to save playback.summaryThresholdSeconds", toError(e));
            });
        },

        setSubtitleContextWindowSeconds: (seconds) => {
            const nextPlayback = { ...get().playback, subtitleContextWindowSeconds: seconds };
            set({ playback: nextPlayback });
            putGlobalConfig({ playback: nextPlayback }).catch((e) => {
                log.error("Failed to save playback.subtitleContextWindowSeconds", toError(e));
            });
        },

        setSubtitleRepeatCount: (count) => {
            const nextPlayback = { ...get().playback, subtitleRepeatCount: count };
            set({ playback: nextPlayback });
            putGlobalConfig({ playback: nextPlayback }).catch((e) => {
                log.error("Failed to save playback.subtitleRepeatCount", toError(e));
            });
        },

        setSubtitleFontSize: (size) => {
            const nextSubtitleDisplay = {
                ...get().subtitleDisplay,
                fontSize: Math.min(Math.max(size, 10), 72),
            };
            set({ subtitleDisplay: nextSubtitleDisplay });
            putGlobalConfig({ subtitleDisplay: nextSubtitleDisplay }).catch((e) => {
                log.error("Failed to save subtitleDisplay.fontSize", toError(e));
            });
        },

        setSubtitleBottomOffset: (offset) => {
            const nextSubtitleDisplay = {
                ...get().subtitleDisplay,
                bottomOffset: Math.min(Math.max(offset, 0), 200),
            };
            set({ subtitleDisplay: nextSubtitleDisplay });
            putGlobalConfig({ subtitleDisplay: nextSubtitleDisplay }).catch((e) => {
                log.error("Failed to save subtitleDisplay.bottomOffset", toError(e));
            });
        },

        setOriginalLanguage: (lang) => {
            const nextLanguage = { ...get().language, original: lang };
            set({ language: nextLanguage });
            putGlobalConfig({ language: nextLanguage }).catch((e) => {
                log.error("Failed to save language.original", toError(e));
            });
        },

        setTranslatedLanguage: (lang) => {
            const nextLanguage = { ...get().language, translated: lang };
            set({ language: nextLanguage });
            putGlobalConfig({ language: nextLanguage }).catch((e) => {
                log.error("Failed to save language.translated", toError(e));
            });
        },

        loadGlobalConfigFromServer: async () => {
            set({ _languageLoading: true });
            try {
                const payload = await getGlobalConfig();
                const merged = mergeSettings(payload, get());
                set({
                    ...merged,
                    _hydrated: true,
                });
            } catch (e) {
                log.error("Failed to load global config from server", toError(e));
                set({ _hydrated: true });
            } finally {
                set({ _languageLoading: false });
            }
        },

        loadLanguageFromServer: async () => {
            await get().loadGlobalConfigFromServer();
        },

        toggleHideSidebars: () => {
            const nextHideSidebars = !get().hideSidebars;
            set({ hideSidebars: nextHideSidebars });
            putGlobalConfig({ hideSidebars: nextHideSidebars }).catch((e) => {
                log.error("Failed to save hideSidebars", toError(e));
            });
        },

        setViewMode: (mode) => {
            set({ viewMode: mode });
            putGlobalConfig({ viewMode: mode }).catch((e) => {
                log.error("Failed to save viewMode", toError(e));
            });
        },

        setBrowserNotificationsEnabled: (value) => {
            const nextNotifications = { ...get().notifications, browserNotificationsEnabled: value };
            set({ notifications: nextNotifications });
            putGlobalConfig({ notifications: nextNotifications }).catch((e) => {
                log.error("Failed to save notifications.browserNotificationsEnabled", toError(e));
            });
        },

        setToastNotificationsEnabled: (value) => {
            const nextNotifications = { ...get().notifications, toastNotificationsEnabled: value };
            set({ notifications: nextNotifications });
            putGlobalConfig({ notifications: nextNotifications }).catch((e) => {
                log.error("Failed to save notifications.toastNotificationsEnabled", toError(e));
            });
        },

        setTitleFlashEnabled: (value) => {
            const nextNotifications = { ...get().notifications, titleFlashEnabled: value };
            set({ notifications: nextNotifications });
            putGlobalConfig({ notifications: nextNotifications }).catch((e) => {
                log.error("Failed to save notifications.titleFlashEnabled", toError(e));
            });
        },

        toggleLive2d: () => {
            const nextLive2d = { ...get().live2d, enabled: !get().live2d.enabled };
            set({ live2d: nextLive2d });
            putGlobalConfig({ live2d: nextLive2d }).catch((e) => {
                log.error("Failed to save live2d.enabled", toError(e));
            });
        },

        setLive2dModelPath: (path) => {
            const nextLive2d = { ...get().live2d, modelPath: path };
            set({ live2d: nextLive2d });
            putGlobalConfig({ live2d: nextLive2d }).catch((e) => {
                log.error("Failed to save live2d.modelPath", toError(e));
            });
        },

        setLive2dModelPosition: (position) => {
            const nextLive2d = { ...get().live2d, modelPosition: position };
            set({ live2d: nextLive2d });
            putGlobalConfig({ live2d: nextLive2d }).catch((e) => {
                log.error("Failed to save live2d.modelPosition", toError(e));
            });
        },

        setLive2dModelScale: (scale) => {
            const nextLive2d = { ...get().live2d, modelScale: scale };
            set({ live2d: nextLive2d });
            putGlobalConfig({ live2d: nextLive2d }).catch((e) => {
                log.error("Failed to save live2d.modelScale", toError(e));
            });
        },

        toggleLive2dSyncWithVideo: () => {
            const nextLive2d = {
                ...get().live2d,
                syncWithVideoAudio: !get().live2d.syncWithVideoAudio,
            };
            set({ live2d: nextLive2d });
            putGlobalConfig({ live2d: nextLive2d }).catch((e) => {
                log.error("Failed to save live2d.syncWithVideoAudio", toError(e));
            });
        },

        setLearnerProfile: (profile) => {
            set({ learnerProfile: profile });
            putGlobalConfig({ learnerProfile: profile }).catch((e) => {
                log.error("Failed to save learnerProfile", toError(e));
            });
        },

        setNoteContextMode: (mode) => {
            const nextNote = { ...get().note, contextMode: mode };
            set({ note: nextNote });
            putGlobalConfig({ note: nextNote }).catch((e) => {
                log.error("Failed to save note.contextMode", toError(e));
            });
        },

        loadNoteDefaultsFromServer: async () => {
            try {
                const data = await getNoteDefaults();
                const nextNote = {
                    ...get().note,
                    contextMode: data.defaultContextMode ?? get().note.contextMode,
                };
                set({ note: nextNote });
            } catch (e) {
                log.error("Failed to load note defaults from server", toError(e));
            }
        },

        setAILlmModel: (model) => {
            const nextAi = { ...get().ai, llmModel: model };
            set({ ai: nextAi });
            putGlobalConfig({ ai: { llmModel: model } }).catch((e) => {
                log.error("Failed to save ai.llmModel", toError(e));
            });
        },

        setAITtsModel: (model) => {
            const nextAi = { ...get().ai, ttsModel: model };
            set({ ai: nextAi });
            putGlobalConfig({ ai: { ttsModel: model } }).catch((e) => {
                log.error("Failed to save ai.ttsModel", toError(e));
            });
        },

        setAILlmTaskModel: (taskKey, model) => {
            const nextTaskModels = {
                ...normalizeTaskModelMap(get().ai.llmTaskModels),
                [taskKey]: model,
            };

            if (nextTaskModels[taskKey] === null) {
                delete nextTaskModels[taskKey];
            }

            const nextAi = {
                ...get().ai,
                llmTaskModels: nextTaskModels,
            };
            set({ ai: nextAi });
            putGlobalConfig({ ai: { llmTaskModels: nextTaskModels } }).catch((e) => {
                log.error("Failed to save ai.llmTaskModels", toError(e));
            });
        },

        setAITtsTaskModel: (taskKey, model) => {
            const nextTaskModels = {
                ...normalizeTaskModelMap(get().ai.ttsTaskModels),
                [taskKey]: model,
            };

            if (nextTaskModels[taskKey] === null) {
                delete nextTaskModels[taskKey];
            }

            const nextAi = {
                ...get().ai,
                ttsTaskModels: nextTaskModels,
            };
            set({ ai: nextAi });
            putGlobalConfig({ ai: { ttsTaskModels: nextTaskModels } }).catch((e) => {
                log.error("Failed to save ai.ttsTaskModels", toError(e));
            });
        },

        setAIPrompt: (funcId, implId) => {
            const nextAi = {
                ...get().ai,
                prompts: { ...get().ai.prompts, [funcId]: implId },
            };
            set({ ai: nextAi });
            putGlobalConfig({ ai: { prompts: nextAi.prompts } }).catch((e) => {
                log.error("Failed to save ai.prompts", toError(e));
            });
        },

        resetAIPrompt: (funcId) => {
            const { [funcId]: _, ...rest } = get().ai.prompts;
            const nextAi = {
                ...get().ai,
                prompts: rest,
            };
            set({ ai: nextAi });
            putGlobalConfig({ ai: { prompts: rest } }).catch((e) => {
                log.error("Failed to reset ai.prompts", toError(e));
            });
        },

        loadAIConfigFromServer: async () => {
            try {
                await getAppConfig();
            } catch (e) {
                log.error("Failed to load AI config from server", toError(e));
            }
        },

        setDictionaryEnabled: (value) => {
            const nextDictionary = { ...get().dictionary, enabled: value };
            set({ dictionary: nextDictionary });
            putGlobalConfig({ dictionary: nextDictionary }).catch((e) => {
                log.error("Failed to save dictionary.enabled", toError(e));
            });
        },

        setDictionaryInteractionMode: (mode) => {
            const nextDictionary = { ...get().dictionary, interactionMode: mode };
            set({ dictionary: nextDictionary });
            putGlobalConfig({ dictionary: nextDictionary }).catch((e) => {
                log.error("Failed to save dictionary.interactionMode", toError(e));
            });
        },

        resetToDefaults: () => {
            const next = mergeSettings(DEFAULT_GLOBAL_SETTINGS, get());
            set({
                ...next,
                _hydrated: true,
            });
            persistGlobalConfig(next).catch((e) => {
                log.error("Failed to reset global config", toError(e));
            });
        },
    })
);

// ─── Scope-Aware Selector Hooks ──────────────────────────────────────────────
//
// These hooks transparently return resolved (merged) values when inside a
// VideoConfigProvider (video page), and global values otherwise (home page).
// Existing consumers don't need to change — they automatically get the right value.

export function usePlaybackSettings() {
    const videoCtx = useVideoConfigOptional();
    const global = useGlobalSettingsStore((s) => s.playback);
    return videoCtx ? videoCtx.resolved.playback : global;
}

export function useLanguageSettings() {
    const videoCtx = useVideoConfigOptional();
    const global = useGlobalSettingsStore((s) => s.language);
    return videoCtx ? videoCtx.resolved.language : global;
}

export function useLive2dSettings() {
    const videoCtx = useVideoConfigOptional();
    const global = useGlobalSettingsStore((s) => s.live2d);
    return videoCtx ? videoCtx.resolved.live2d : global;
}

export function useNotificationSettings() {
    const videoCtx = useVideoConfigOptional();
    const global = useGlobalSettingsStore((s) => s.notifications);
    return videoCtx ? videoCtx.resolved.notifications : global;
}

export function useLearnerProfile() {
    const videoCtx = useVideoConfigOptional();
    const global = useGlobalSettingsStore((s) => s.learnerProfile);
    return videoCtx ? videoCtx.resolved.learnerProfile : global;
}

export function useNoteSettings() {
    const videoCtx = useVideoConfigOptional();
    const global = useGlobalSettingsStore((s) => s.note);
    return videoCtx ? videoCtx.resolved.note : global;
}

export const useIsHydrated = () =>
    useGlobalSettingsStore((state) => state._hydrated);

export function useAISettings() {
    const videoCtx = useVideoConfigOptional();
    const global = useGlobalSettingsStore((s) => s.ai);
    return videoCtx ? videoCtx.resolved.ai : global;
}

export function useViewMode() {
    const videoCtx = useVideoConfigOptional();
    const global = useGlobalSettingsStore((s) => s.viewMode);
    return videoCtx ? videoCtx.resolved.viewMode : global;
}

export function useDictionarySettings() {
    const videoCtx = useVideoConfigOptional();
    const global = useGlobalSettingsStore((s) => s.dictionary);
    return videoCtx ? videoCtx.resolved.dictionary : global;
}

export function useSubtitleDisplaySettings() {
    const videoCtx = useVideoConfigOptional();
    const global = useGlobalSettingsStore((s) => s.subtitleDisplay);
    return videoCtx ? videoCtx.resolved.subtitleDisplay : global;
}

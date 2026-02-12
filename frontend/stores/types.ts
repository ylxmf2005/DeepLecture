"use client";

// Direct env access to avoid circular dependency with @/lib/api
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:11393";

/**
 * Zustand Store Type Definitions
 *
 * Two stores architecture:
 * 1. GlobalSettingsStore - user-level preferences (persisted globally)
 * 2. VideoStateStore - per-video state (persisted per videoId)
 */

export interface Live2DSettings {
    enabled: boolean;
    modelPath: string;
    modelPosition: { x: number; y: number };
    modelScale: number;
    syncWithVideoAudio: boolean;
}

export interface LanguageSettings {
    /** Source language (video audio language for Whisper transcription) */
    original: string;
    /** Target language (used for translations, AI explanations, timelines, notes) */
    translated: string;
}

export interface PlaybackSettings {
    autoPauseOnLeave: boolean;
    autoResumeOnReturn: boolean;
    autoSwitchSubtitlesOnLeave: boolean;
    summaryThresholdSeconds: number;
    subtitleContextWindowSeconds: number;
    subtitleRepeatCount: number;
}

export interface SubtitleDisplaySettings {
    fontSize: number;
    bottomOffset: number;
}

export interface NotificationSettings {
    browserNotificationsEnabled: boolean;
    toastNotificationsEnabled: boolean;
    titleFlashEnabled: boolean;
}

export type NoteContextMode = "subtitle" | "slide" | "both";

export interface NoteSettings {
    contextMode: NoteContextMode;
}

export interface AISettings {
    llmModel: string | null;
    ttsModel: string | null;
    llmTaskModels?: Record<string, string | null>;
    ttsTaskModels?: Record<string, string | null>;
    prompts: Record<string, string>;
}

export type DictionaryInteractionMode = "hover" | "click";

export interface DictionarySettings {
    enabled: boolean;
    interactionMode: DictionaryInteractionMode;
}

export interface GlobalSettings {
    playback: PlaybackSettings;
    language: LanguageSettings;
    hideSidebars: boolean;
    viewMode: ViewMode;
    subtitleDisplay: SubtitleDisplaySettings;
    notifications: NotificationSettings;
    live2d: Live2DSettings;
    learnerProfile: string;
    note: NoteSettings;
    ai: AISettings;
    dictionary: DictionarySettings;
}

export const DEFAULT_GLOBAL_SETTINGS: GlobalSettings = {
    playback: {
        autoPauseOnLeave: false,
        autoResumeOnReturn: false,
        autoSwitchSubtitlesOnLeave: false,
        summaryThresholdSeconds: 60,
        subtitleContextWindowSeconds: 30,
        subtitleRepeatCount: 1,
    },
    subtitleDisplay: {
        fontSize: 16,
        bottomOffset: 56,
    },
    notifications: {
        browserNotificationsEnabled: false,
        toastNotificationsEnabled: true,
        titleFlashEnabled: true,
    },
    language: {
        original: "en",
        translated: "zh",
    },
    hideSidebars: false,
    viewMode: "normal",
    live2d: {
        enabled: false,
        modelPath: `${API_BASE_URL}/api/live2d/models/Haru/Haru.model3.json`,
        modelPosition: { x: 0, y: 0 },
        modelScale: 1.0,
        syncWithVideoAudio: true,
    },
    learnerProfile: "",
    note: {
        contextMode: "both",
    },
    ai: {
        llmModel: null,
        ttsModel: null,
        prompts: {},
    },
    dictionary: {
        enabled: true,
        interactionMode: "hover",
    },
};

/**
 * Semantic subtitle display mode (language-agnostic).
 * - source: Show only source language subtitles
 * - target: Show only target language subtitles
 * - dual: Show source on top, target below
 * - dual_reversed: Show target on top, source below
 */
export type SubtitleDisplayMode = "source" | "target" | "dual" | "dual_reversed";

/**
 * Video player view mode for layout control.
 * - normal: Default layout (video + sidebar side by side)
 * - widescreen: Video full width, sidebar + notes below
 * - web-fullscreen: Video fills browser viewport
 * - fullscreen: Native browser fullscreen API
 */
export type ViewMode = "normal" | "widescreen" | "web-fullscreen" | "fullscreen";

export interface VideoNotes {
    draft: string;
    dirty: boolean;
    lastSyncedAt: string | null;
}

export interface VideoDeck {
    id: string;
    name: string;
}

export interface VideoState {
    subtitleModePlayer: SubtitleDisplayMode;
    subtitleModeSidebar: SubtitleDisplayMode;
    smartSkipEnabled: boolean;
    progressSeconds: number | null;
    deck: VideoDeck | null;
    notes: VideoNotes;
    selectedVoiceoverId: string | null;
    /** Quick toggle preset: Original track (null = video original audio, string = voiceover ID) */
    quickToggleOriginalVoiceoverId: string | null;
    /** Quick toggle preset: Translated track (null = not set, string = voiceover ID) */
    quickToggleTranslatedVoiceoverId: string | null;
}

export const EMPTY_VIDEO_NOTES: VideoNotes = Object.freeze({
    draft: "",
    dirty: false,
    lastSyncedAt: null,
});

export const DEFAULT_VIDEO_STATE: VideoState = {
    subtitleModePlayer: "source",
    subtitleModeSidebar: "source",
    smartSkipEnabled: false,
    progressSeconds: null,
    deck: null,
    notes: EMPTY_VIDEO_NOTES,
    selectedVoiceoverId: null,
    quickToggleOriginalVoiceoverId: null,
    quickToggleTranslatedVoiceoverId: null,
};

export interface GlobalSettingsActions {
    setAutoPauseOnLeave: (value: boolean) => void;
    setAutoResumeOnReturn: (value: boolean) => void;
    setAutoSwitchSubtitlesOnLeave: (value: boolean) => void;
    setSummaryThresholdSeconds: (seconds: number) => void;
    setSubtitleContextWindowSeconds: (seconds: number) => void;
    setSubtitleRepeatCount: (count: number) => void;
    setSubtitleFontSize: (size: number) => void;
    setSubtitleBottomOffset: (offset: number) => void;
    setOriginalLanguage: (lang: string) => void;
    setTranslatedLanguage: (lang: string) => void;
    loadLanguageFromServer: () => Promise<void>;
    toggleHideSidebars: () => void;
    setViewMode: (mode: ViewMode) => void;
    setBrowserNotificationsEnabled: (value: boolean) => void;
    setToastNotificationsEnabled: (value: boolean) => void;
    setTitleFlashEnabled: (value: boolean) => void;
    toggleLive2d: () => void;
    setLive2dModelPath: (path: string) => void;
    setLive2dModelPosition: (position: { x: number; y: number }) => void;
    setLive2dModelScale: (scale: number) => void;
    toggleLive2dSyncWithVideo: () => void;
    setLearnerProfile: (profile: string) => void;
    setNoteContextMode: (mode: NoteContextMode) => void;
    loadNoteDefaultsFromServer: () => Promise<void>;
    setAILlmModel: (model: string | null) => void;
    setAITtsModel: (model: string | null) => void;
    setAIPrompt: (funcId: string, implId: string) => void;
    resetAIPrompt: (funcId: string) => void;
    loadAIConfigFromServer: () => Promise<void>;
    setDictionaryEnabled: (value: boolean) => void;
    setDictionaryInteractionMode: (mode: DictionaryInteractionMode) => void;
    resetToDefaults: () => void;
}

export interface VideoStateActions {
    getVideoState: (videoId: string) => VideoState;
    setSubtitleModePlayer: (videoId: string, mode: SubtitleDisplayMode) => void;
    setSubtitleModeSidebar: (videoId: string, mode: SubtitleDisplayMode) => void;
    setSmartSkipEnabled: (videoId: string, enabled: boolean) => void;
    toggleSmartSkip: (videoId: string) => void;
    setProgress: (videoId: string, seconds: number) => void;
    clearProgress: (videoId: string) => void;
    setDeck: (videoId: string, deck: VideoDeck | null) => void;
    setNotesDraft: (videoId: string, draft: string) => void;
    markNotesSynced: (videoId: string) => void;
    setSelectedVoiceoverId: (videoId: string, voiceoverId: string | null) => void;
    setQuickToggleOriginalVoiceoverId: (videoId: string, voiceoverId: string | null) => void;
    setQuickToggleTranslatedVoiceoverId: (videoId: string, voiceoverId: string | null) => void;
    clearVideoState: (videoId: string) => void;
    clearAllVideoStates: () => void;
}

export const STORAGE_KEYS = {
    GLOBAL_SETTINGS: "courseSubtitle:global-settings",
    VIDEO_STATE: "courseSubtitle:video-state",
} as const;

export const STORAGE_VERSIONS = {
    GLOBAL_SETTINGS: 3, // Bumped: added ai settings (llmModel, ttsModel, prompts)
    VIDEO_STATE: 2, // Bumped for semantic subtitle mode migration (en/zh → source/target/dual/dual_reversed)
} as const;

export type PerVideoConfig = Partial<GlobalSettings>;

/** Maps legacy subtitle mode values to semantic equivalents */
export const LEGACY_SUBTITLE_MODE_MAP: Record<string, SubtitleDisplayMode> = {
    en: "source",
    zh: "target",
    en_zh: "dual",
    zh_en: "dual_reversed",
    // Also accept new values for forward compat
    source: "source",
    target: "target",
    dual: "dual",
    dual_reversed: "dual_reversed",
};

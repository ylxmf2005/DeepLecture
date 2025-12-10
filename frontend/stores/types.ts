"use client";

import { API_BASE_URL } from "@/lib/api";

/**
 * Zustand Store Type Definitions
 *
 * Two stores architecture:
 * 1. GlobalSettingsStore - user-level preferences (persisted globally)
 * 2. VideoStateStore - per-video state (persisted per videoId)
 */

// =============================================================================
// Global Settings (user-level, single localStorage key)
// =============================================================================

export interface Live2DSettings {
    enabled: boolean;
    modelPath: string;
    modelPosition: { x: number; y: number };
    modelScale: number;
    syncWithVideoAudio: boolean;
}

export interface LanguageSettings {
    original: string;      // e.g., "en"
    ai: string;            // e.g., "zh"
    translated: string;    // e.g., "zh"
}

export interface PlaybackSettings {
    autoPauseOnLeave: boolean;
    autoResumeOnReturn: boolean;
    summaryThresholdSeconds: number;
    subtitleContextWindowSeconds: number;
    subtitleRepeatCount: number;
}

export interface SubtitleDisplaySettings {
    // Base font size in pixels for subtitles in normal (non-fullscreen) mode
    fontSize: number;
    // Vertical offset from the bottom of the video in pixels
    bottomOffset: number;
}

export interface NotificationSettings {
    // Enable browser notifications (requires permission)
    browserNotificationsEnabled: boolean;
    // Enable toast notifications in-app
    toastNotificationsEnabled: boolean;
    // Enable title flash when tab is in background
    titleFlashEnabled: boolean;
}

export interface GlobalSettings {
    // Playback behavior
    playback: PlaybackSettings;

    // Language preferences (also synced to server)
    language: LanguageSettings;

    // UI preferences
    hideSidebars: boolean;

    // Subtitle display preferences (applies to all videos)
    subtitleDisplay: SubtitleDisplaySettings;

    // Notification preferences
    notifications: NotificationSettings;

    // Live2D avatar settings
    live2d: Live2DSettings;

    // AI context / learner profile
    learnerProfile: string;
}

export const DEFAULT_GLOBAL_SETTINGS: GlobalSettings = {
    playback: {
        autoPauseOnLeave: false,
        autoResumeOnReturn: false,
        summaryThresholdSeconds: 60,
        subtitleContextWindowSeconds: 30,
        subtitleRepeatCount: 1,
    },
    subtitleDisplay: {
        fontSize: 16,
        bottomOffset: 56, // roughly Tailwind bottom-14 (3.5rem)
    },
    notifications: {
        browserNotificationsEnabled: false,
        toastNotificationsEnabled: true,
        titleFlashEnabled: true,
    },
    language: {
        original: "en",
        ai: "zh",
        translated: "zh",
    },
    hideSidebars: false,
    live2d: {
        enabled: false,
        modelPath: `${API_BASE_URL}/api/live2d/models/Haru/Haru.model3.json`,
        modelPosition: { x: 0, y: 0 },
        modelScale: 1.0,
        syncWithVideoAudio: true,
    },
    learnerProfile: "",
};

// =============================================================================
// Per-Video State (keyed by videoId)
// =============================================================================

export type SubtitleMode = "en" | "zh" | "en_zh" | "zh_en";

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
    // Subtitle display preferences
    subtitleModePlayer: SubtitleMode;
    subtitleModeSidebar: SubtitleMode;

    // Smart Skip toggle (per-video because it depends on timeline)
    smartSkipEnabled: boolean;

    // Playback progress (seconds)
    progressSeconds: number | null;

    // Attached slide deck
    deck: VideoDeck | null;

    // Notes (local draft with server sync)
    notes: VideoNotes;
}

export const DEFAULT_VIDEO_STATE: VideoState = {
    subtitleModePlayer: "en",
    subtitleModeSidebar: "en",
    smartSkipEnabled: false,
    progressSeconds: null,
    deck: null,
    notes: {
        draft: "",
        dirty: false,
        lastSyncedAt: null,
    },
};

// =============================================================================
// Store Actions
// =============================================================================

export interface GlobalSettingsActions {
    // Playback
    setAutoPauseOnLeave: (value: boolean) => void;
    setAutoResumeOnReturn: (value: boolean) => void;
    setSummaryThresholdSeconds: (seconds: number) => void;
    setSubtitleContextWindowSeconds: (seconds: number) => void;
    setSubtitleRepeatCount: (count: number) => void;

    // Subtitle display
    setSubtitleFontSize: (size: number) => void;
    setSubtitleBottomOffset: (offset: number) => void;

    // Language (local state, loaded from server on init)
    setOriginalLanguage: (lang: string) => void;
    setAiLanguage: (lang: string) => void;
    setTranslatedLanguage: (lang: string) => void;
    loadLanguageFromServer: () => Promise<void>;

    // UI
    toggleHideSidebars: () => void;

    // Notifications
    setBrowserNotificationsEnabled: (value: boolean) => void;
    setToastNotificationsEnabled: (value: boolean) => void;
    setTitleFlashEnabled: (value: boolean) => void;

    // Live2D
    toggleLive2d: () => void;
    setLive2dModelPath: (path: string) => void;
    setLive2dModelPosition: (position: { x: number; y: number }) => void;
    setLive2dModelScale: (scale: number) => void;
    toggleLive2dSyncWithVideo: () => void;

    // Learner profile
    setLearnerProfile: (profile: string) => void;

    // Reset
    resetToDefaults: () => void;
}

export interface VideoStateActions {
    // Get or initialize state for a video
    getVideoState: (videoId: string) => VideoState;

    // Subtitle mode
    setSubtitleModePlayer: (videoId: string, mode: SubtitleMode) => void;
    setSubtitleModeSidebar: (videoId: string, mode: SubtitleMode) => void;

    // Smart Skip
    setSmartSkipEnabled: (videoId: string, enabled: boolean) => void;
    toggleSmartSkip: (videoId: string) => void;

    // Progress
    setProgress: (videoId: string, seconds: number) => void;
    clearProgress: (videoId: string) => void;

    // Deck
    setDeck: (videoId: string, deck: VideoDeck | null) => void;

    // Notes
    setNotesDraft: (videoId: string, draft: string) => void;
    markNotesSynced: (videoId: string) => void;

    // Cleanup
    clearVideoState: (videoId: string) => void;
    clearAllVideoStates: () => void;
}

// =============================================================================
// Storage Keys & Versioning
// =============================================================================

export const STORAGE_KEYS = {
    GLOBAL_SETTINGS: "courseSubtitle:global-settings",
    VIDEO_STATE: "courseSubtitle:video-state",
} as const;

export const STORAGE_VERSIONS = {
    GLOBAL_SETTINGS: 1,
    VIDEO_STATE: 1,
} as const;

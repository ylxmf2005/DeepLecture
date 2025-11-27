"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import {
    VideoState,
    VideoStateActions,
    DEFAULT_VIDEO_STATE,
    STORAGE_KEYS,
    STORAGE_VERSIONS,
} from "./types";

interface VideoStateStoreState {
    videos: Record<string, VideoState>;
    _hydrated: boolean;
}

type VideoStateStore = VideoStateStoreState & VideoStateActions;

export const useVideoStateStore = create<VideoStateStore>()(
    persist(
        (set, get) => ({
            videos: {},
            _hydrated: false,

            getVideoState: (videoId) => {
                const state = get();
                return state.videos[videoId] ?? DEFAULT_VIDEO_STATE;
            },

            setSubtitleModePlayer: (videoId, mode) =>
                set((state) => ({
                    videos: {
                        ...state.videos,
                        [videoId]: {
                            ...DEFAULT_VIDEO_STATE,
                            ...state.videos[videoId],
                            subtitleModePlayer: mode,
                        },
                    },
                })),

            setSubtitleModeSidebar: (videoId, mode) =>
                set((state) => ({
                    videos: {
                        ...state.videos,
                        [videoId]: {
                            ...DEFAULT_VIDEO_STATE,
                            ...state.videos[videoId],
                            subtitleModeSidebar: mode,
                        },
                    },
                })),

            setSmartSkipEnabled: (videoId, enabled) =>
                set((state) => ({
                    videos: {
                        ...state.videos,
                        [videoId]: {
                            ...DEFAULT_VIDEO_STATE,
                            ...state.videos[videoId],
                            smartSkipEnabled: enabled,
                        },
                    },
                })),

            toggleSmartSkip: (videoId) =>
                set((state) => {
                    const current = state.videos[videoId] ?? DEFAULT_VIDEO_STATE;
                    return {
                        videos: {
                            ...state.videos,
                            [videoId]: {
                                ...DEFAULT_VIDEO_STATE,
                                ...current,
                                smartSkipEnabled: !current.smartSkipEnabled,
                            },
                        },
                    };
                }),

            setProgress: (videoId, seconds) =>
                set((state) => ({
                    videos: {
                        ...state.videos,
                        [videoId]: {
                            ...DEFAULT_VIDEO_STATE,
                            ...state.videos[videoId],
                            progressSeconds: seconds,
                        },
                    },
                })),

            clearProgress: (videoId) =>
                set((state) => ({
                    videos: {
                        ...state.videos,
                        [videoId]: {
                            ...DEFAULT_VIDEO_STATE,
                            ...state.videos[videoId],
                            progressSeconds: null,
                        },
                    },
                })),

            setDeck: (videoId, deck) =>
                set((state) => ({
                    videos: {
                        ...state.videos,
                        [videoId]: {
                            ...DEFAULT_VIDEO_STATE,
                            ...state.videos[videoId],
                            deck,
                        },
                    },
                })),

            setNotesDraft: (videoId, draft) =>
                set((state) => ({
                    videos: {
                        ...state.videos,
                        [videoId]: {
                            ...DEFAULT_VIDEO_STATE,
                            ...state.videos[videoId],
                            notes: {
                                ...(state.videos[videoId]?.notes ?? DEFAULT_VIDEO_STATE.notes),
                                draft,
                                dirty: true,
                            },
                        },
                    },
                })),

            markNotesSynced: (videoId) =>
                set((state) => ({
                    videos: {
                        ...state.videos,
                        [videoId]: {
                            ...DEFAULT_VIDEO_STATE,
                            ...state.videos[videoId],
                            notes: {
                                ...(state.videos[videoId]?.notes ?? DEFAULT_VIDEO_STATE.notes),
                                dirty: false,
                                lastSyncedAt: new Date().toISOString(),
                            },
                        },
                    },
                })),

            clearVideoState: (videoId) =>
                set((state) => {
                    const { [videoId]: _, ...rest } = state.videos;
                    return { videos: rest };
                }),

            clearAllVideoStates: () => set({ videos: {} }),
        }),
        {
            name: STORAGE_KEYS.VIDEO_STATE,
            version: STORAGE_VERSIONS.VIDEO_STATE,
            storage: createJSONStorage(() => localStorage),

            partialize: (state) => ({
                videos: state.videos,
            }),

            onRehydrateStorage: () => () => {
                useVideoStateStore.setState({ _hydrated: true });
            },

            migrate: (persistedState) => {
                if (!persistedState) {
                    return {
                        videos: {},
                        _hydrated: false,
                    };
                }
                return persistedState as VideoStateStoreState;
            },
        }
    )
);

// Selector hooks for common use cases
export const useVideoProgress = (videoId: string) =>
    useVideoStateStore((state) => state.videos[videoId]?.progressSeconds ?? null);

export const usePlayerSubtitleMode = (videoId: string) =>
    useVideoStateStore((state) => state.videos[videoId]?.subtitleModePlayer ?? DEFAULT_VIDEO_STATE.subtitleModePlayer);

export const useSidebarSubtitleMode = (videoId: string) =>
    useVideoStateStore((state) => state.videos[videoId]?.subtitleModeSidebar ?? DEFAULT_VIDEO_STATE.subtitleModeSidebar);

export const useSmartSkipEnabled = (videoId: string) =>
    useVideoStateStore((state) => state.videos[videoId]?.smartSkipEnabled ?? false);

export const useVideoDeck = (videoId: string) =>
    useVideoStateStore((state) => state.videos[videoId]?.deck ?? null);

// Return a new object to avoid mutation of shared constant
export const useVideoNotes = (videoId: string) =>
    useVideoStateStore((state) => {
        const notes = state.videos[videoId]?.notes;
        if (notes) return notes;
        // Return a new object each time to prevent mutation of defaults
        return { draft: "", dirty: false, lastSyncedAt: null };
    });

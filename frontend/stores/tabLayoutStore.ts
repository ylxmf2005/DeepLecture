"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { useEffect, useState } from "react";

export type TabId =
    | "subtitles"
    | "explanations"
    | "timeline"
    | "ask"
    | "verify"
    | "bookmarks"
    | "notes"
    | "flashcard"
    | "test"
    | "report"
    | "cheatsheet"
    | "quiz"
    | "podcast";

export type PanelId = "sidebar" | "bottom";

interface DragSnapshot {
    panels: {
        sidebar: TabId[];
        bottom: TabId[];
    };
    activeTabs: {
        sidebar: TabId;
        bottom: TabId;
    };
}

interface TabLayoutState {
    panels: {
        sidebar: TabId[];
        bottom: TabId[];
    };
    activeTabs: {
        sidebar: TabId;
        bottom: TabId;
    };
    _dragSnapshot: DragSnapshot | null;
    _hasHydrated: boolean;
    setHasHydrated: (value: boolean) => void;
    moveTab: (tabId: TabId, sourcePanel: PanelId, targetPanel: PanelId, newIndex: number) => void;
    reorderTab: (panel: PanelId, oldIndex: number, newIndex: number) => void;
    setActiveTab: (panel: PanelId, tabId: TabId) => void;
    resetLayout: () => void;
    startDrag: () => void;
    commitDrag: () => void;
    rollbackDrag: () => void;
}

const DEFAULT_SIDEBAR_TABS: TabId[] = ["subtitles", "explanations", "timeline", "ask"];
const DEFAULT_BOTTOM_TABS: TabId[] = ["verify", "notes", "bookmarks", "flashcard", "quiz", "test", "report", "cheatsheet", "podcast"];
const ALL_TABS = new Set<TabId>([...DEFAULT_SIDEBAR_TABS, ...DEFAULT_BOTTOM_TABS]);

export const LAYOUT_CONSTRAINTS = {
    MAX_SIDEBAR_TABS: 4,
    MAX_BOTTOM_TABS: 10,
} as const;

const MAX_SIDEBAR_TABS = LAYOUT_CONSTRAINTS.MAX_SIDEBAR_TABS;
const MAX_BOTTOM_TABS = LAYOUT_CONSTRAINTS.MAX_BOTTOM_TABS;

export const useTabLayoutStore = create<TabLayoutState>()(
    persist(
        (set, get) => ({
            panels: {
                sidebar: DEFAULT_SIDEBAR_TABS,
                bottom: DEFAULT_BOTTOM_TABS,
            },
            activeTabs: {
                sidebar: "subtitles",
                bottom: "verify",
            },
            _dragSnapshot: null,
            _hasHydrated: false,
            setHasHydrated: (value) => set({ _hasHydrated: value }),
            startDrag: () => {
                const { panels, activeTabs } = get();
                set({
                    _dragSnapshot: {
                        panels: {
                            sidebar: [...panels.sidebar],
                            bottom: [...panels.bottom],
                        },
                        activeTabs: { ...activeTabs },
                    },
                });
            },
            commitDrag: () => {
                set({ _dragSnapshot: null });
            },
            rollbackDrag: () => {
                const { _dragSnapshot } = get();
                if (_dragSnapshot) {
                    set({
                        panels: _dragSnapshot.panels,
                        activeTabs: _dragSnapshot.activeTabs,
                        _dragSnapshot: null,
                    });
                }
            },
            moveTab: (tabId, sourcePanel, targetPanel, newIndex) => {
                const { panels, activeTabs } = get();

                if (sourcePanel === targetPanel) {
                    const list = panels[sourcePanel];
                    const oldIndex = list.indexOf(tabId);
                    if (oldIndex !== -1) {
                        get().reorderTab(sourcePanel, oldIndex, newIndex);
                    }
                    return;
                }

                const maxTarget = targetPanel === "sidebar" ? MAX_SIDEBAR_TABS : MAX_BOTTOM_TABS;
                if (panels[targetPanel].length >= maxTarget) {
                    return;
                }

                const sourceList = [...panels[sourcePanel]];
                const targetList = [...panels[targetPanel]];

                const oldIndex = sourceList.indexOf(tabId);
                if (oldIndex === -1) return;

                sourceList.splice(oldIndex, 1);

                const safeIndex = Math.min(newIndex, targetList.length);
                targetList.splice(safeIndex, 0, tabId);

                const newActiveTabs = { ...activeTabs };

                if (activeTabs[sourcePanel] === tabId && sourceList.length > 0) {
                    newActiveTabs[sourcePanel] = sourceList[0];
                }

                newActiveTabs[targetPanel] = tabId;

                set({
                    panels: {
                        ...panels,
                        [sourcePanel]: sourceList,
                        [targetPanel]: targetList,
                    },
                    activeTabs: newActiveTabs,
                });
            },
            reorderTab: (panel, oldIndex, newIndex) => {
                const { panels } = get();
                const list = [...panels[panel]];

                if (oldIndex < 0 || oldIndex >= list.length) return;
                if (newIndex < 0) return;
                if (oldIndex === newIndex) return;

                const [removed] = list.splice(oldIndex, 1);
                const safeIndex = Math.min(newIndex, list.length);
                list.splice(safeIndex, 0, removed);

                set({
                    panels: {
                        ...panels,
                        [panel]: list,
                    },
                });
            },
            setActiveTab: (panel, tabId) => {
                const { panels } = get();
                if (!panels[panel].includes(tabId)) return;

                set((state) => ({
                    activeTabs: {
                        ...state.activeTabs,
                        [panel]: tabId,
                    },
                }));
            },
            resetLayout: () => {
                set({
                    panels: {
                        sidebar: DEFAULT_SIDEBAR_TABS,
                        bottom: DEFAULT_BOTTOM_TABS,
                    },
                    activeTabs: {
                        sidebar: "subtitles",
                        bottom: "verify",
                    },
                });
            },
        }),
        {
            name: "courseSubtitle:tab-layout",
            storage: createJSONStorage(() => localStorage),
            partialize: (state) => ({
                panels: state.panels,
                activeTabs: state.activeTabs,
            }),
            merge: (persistedState, currentState) => {
                const persisted = persistedState as Partial<TabLayoutState> | undefined;
                if (!persisted?.panels) return currentState;

                // Filter out tabs that no longer exist (removed in a code update)
                const persistedSidebar = (persisted.panels.sidebar || []).filter(tab => ALL_TABS.has(tab));
                const persistedBottom = (persisted.panels.bottom || []).filter(tab => ALL_TABS.has(tab));
                const presentTabs = new Set([...persistedSidebar, ...persistedBottom]);

                // Insert missing tabs at their default positions, not at the end
                const mergedSidebar = [...persistedSidebar];
                const mergedBottom = [...persistedBottom];

                for (const tab of DEFAULT_SIDEBAR_TABS) {
                    if (!presentTabs.has(tab)) {
                        const defaultIndex = DEFAULT_SIDEBAR_TABS.indexOf(tab);
                        const insertAt = Math.min(defaultIndex, mergedSidebar.length);
                        mergedSidebar.splice(insertAt, 0, tab);
                        presentTabs.add(tab);
                    }
                }

                for (const tab of DEFAULT_BOTTOM_TABS) {
                    if (!presentTabs.has(tab)) {
                        const defaultIndex = DEFAULT_BOTTOM_TABS.indexOf(tab);
                        const insertAt = Math.min(defaultIndex, mergedBottom.length);
                        mergedBottom.splice(insertAt, 0, tab);
                        presentTabs.add(tab);
                    }
                }

                return {
                    ...currentState,
                    panels: {
                        sidebar: mergedSidebar,
                        bottom: mergedBottom,
                    },
                    activeTabs: persisted.activeTabs || currentState.activeTabs,
                };
            },
            onRehydrateStorage: () => (state) => {
                state?.setHasHydrated(true);
            },
        }
    )
);

/**
 * Hook to wait for localStorage hydration before rendering.
 * Prevents flash of default content before persisted state loads.
 */
export function useTabLayoutHydrated(): boolean {
    const storeHydrated = useTabLayoutStore((state) => state._hasHydrated);
    const [hydrated, setHydrated] = useState(false);

    useEffect(() => {
        // Also handle SSR: on client mount, check if already hydrated
        const unsubFinishHydration = useTabLayoutStore.persist.onFinishHydration(() => {
            setHydrated(true);
        });
        // If already hydrated (e.g., fast refresh), set immediately
        if (useTabLayoutStore.persist.hasHydrated()) {
            setHydrated(true);
        }
        return unsubFinishHydration;
    }, []);

    return hydrated || storeHydrated;
}

export function findTabPanel(panels: TabLayoutState["panels"], tabId: TabId): PanelId | null {
    if (panels.sidebar.includes(tabId)) return "sidebar";
    if (panels.bottom.includes(tabId)) return "bottom";
    return null;
}

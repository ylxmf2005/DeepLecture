"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

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
    | "podcast"
    | "readAloud";

export type PanelId = "sidebar" | "bottom";
type PanelTabs = {
    sidebar: TabId[];
    bottom: TabId[];
};
type ActiveTabs = {
    sidebar: TabId;
    bottom: TabId;
};

interface DragSnapshot {
    panels: PanelTabs;
    activeTabs: ActiveTabs;
    mountedTabs: PanelTabs;
}

interface TabLayoutState {
    panels: PanelTabs;
    activeTabs: ActiveTabs;
    mountedTabs: PanelTabs;
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
const DEFAULT_BOTTOM_TABS: TabId[] = ["verify", "notes", "readAloud", "bookmarks", "flashcard", "quiz", "test", "report", "cheatsheet", "podcast"];
const ALL_TABS = new Set<TabId>([...DEFAULT_SIDEBAR_TABS, ...DEFAULT_BOTTOM_TABS]);
const DEFAULT_ACTIVE_TABS: ActiveTabs = { sidebar: "subtitles", bottom: "verify" };
const DEFAULT_MOUNTED_TABS: PanelTabs = { sidebar: ["subtitles"], bottom: ["verify"] };

export const LAYOUT_CONSTRAINTS = {
    MAX_SIDEBAR_TABS: 4,
    MAX_BOTTOM_TABS: 11,
} as const;

const MAX_SIDEBAR_TABS = LAYOUT_CONSTRAINTS.MAX_SIDEBAR_TABS;
const MAX_BOTTOM_TABS = LAYOUT_CONSTRAINTS.MAX_BOTTOM_TABS;

function normalizeMountedTabs(panels: PanelTabs, activeTabs: ActiveTabs, mountedTabs: PanelTabs): PanelTabs {
    const sidebar = mountedTabs.sidebar.filter((tabId) => panels.sidebar.includes(tabId));
    const bottom = mountedTabs.bottom.filter((tabId) => panels.bottom.includes(tabId));

    if (panels.sidebar.includes(activeTabs.sidebar) && !sidebar.includes(activeTabs.sidebar)) {
        sidebar.push(activeTabs.sidebar);
    }
    if (panels.bottom.includes(activeTabs.bottom) && !bottom.includes(activeTabs.bottom)) {
        bottom.push(activeTabs.bottom);
    }

    return { sidebar, bottom };
}

function normalizeActiveTabs(panels: PanelTabs, activeTabs: ActiveTabs): ActiveTabs {
    const sidebar = panels.sidebar.includes(activeTabs.sidebar) ? activeTabs.sidebar : (panels.sidebar[0] ?? DEFAULT_ACTIVE_TABS.sidebar);
    const bottom = panels.bottom.includes(activeTabs.bottom) ? activeTabs.bottom : (panels.bottom[0] ?? DEFAULT_ACTIVE_TABS.bottom);
    return { sidebar, bottom };
}

export const useTabLayoutStore = create<TabLayoutState>()(
    persist(
        (set, get) => ({
            panels: {
                sidebar: [...DEFAULT_SIDEBAR_TABS],
                bottom: [...DEFAULT_BOTTOM_TABS],
            },
            activeTabs: { ...DEFAULT_ACTIVE_TABS },
            mountedTabs: {
                sidebar: [...DEFAULT_MOUNTED_TABS.sidebar],
                bottom: [...DEFAULT_MOUNTED_TABS.bottom],
            },
            _dragSnapshot: null,
            _hasHydrated: false,
            setHasHydrated: (value) => set({ _hasHydrated: value }),
            startDrag: () => {
                const { panels, activeTabs, mountedTabs } = get();
                set({
                    _dragSnapshot: {
                        panels: {
                            sidebar: [...panels.sidebar],
                            bottom: [...panels.bottom],
                        },
                        activeTabs: { ...activeTabs },
                        mountedTabs: {
                            sidebar: [...mountedTabs.sidebar],
                            bottom: [...mountedTabs.bottom],
                        },
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
                        mountedTabs: _dragSnapshot.mountedTabs,
                        _dragSnapshot: null,
                    });
                }
            },
            moveTab: (tabId, sourcePanel, targetPanel, newIndex) => {
                const { panels, activeTabs, mountedTabs } = get();

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
                const nextPanels: PanelTabs = {
                    ...panels,
                    [sourcePanel]: sourceList,
                    [targetPanel]: targetList,
                };

                if (activeTabs[sourcePanel] === tabId && sourceList.length > 0) {
                    newActiveTabs[sourcePanel] = sourceList[0];
                }

                newActiveTabs[targetPanel] = tabId;
                const normalizedActiveTabs = normalizeActiveTabs(nextPanels, newActiveTabs);
                const nextMountedTabs = normalizeMountedTabs(nextPanels, normalizedActiveTabs, {
                    ...mountedTabs,
                    [sourcePanel]: mountedTabs[sourcePanel].filter((id) => id !== tabId && sourceList.includes(id)),
                    [targetPanel]: mountedTabs[targetPanel].filter((id) => targetList.includes(id)),
                });

                set({
                    panels: nextPanels,
                    activeTabs: normalizedActiveTabs,
                    mountedTabs: nextMountedTabs,
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
                    activeTabs: normalizeActiveTabs(state.panels, {
                        ...state.activeTabs,
                        [panel]: tabId,
                    }),
                    mountedTabs: normalizeMountedTabs(state.panels, {
                        ...state.activeTabs,
                        [panel]: tabId,
                    }, state.mountedTabs),
                }));
            },
            resetLayout: () => {
                set({
                    panels: {
                        sidebar: [...DEFAULT_SIDEBAR_TABS],
                        bottom: [...DEFAULT_BOTTOM_TABS],
                    },
                    activeTabs: { ...DEFAULT_ACTIVE_TABS },
                    mountedTabs: {
                        sidebar: [...DEFAULT_MOUNTED_TABS.sidebar],
                        bottom: [...DEFAULT_MOUNTED_TABS.bottom],
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

                const mergedPanels: PanelTabs = {
                    sidebar: mergedSidebar,
                    bottom: mergedBottom,
                };
                const persistedActiveTabs: ActiveTabs = {
                    sidebar: persisted.activeTabs?.sidebar ?? currentState.activeTabs.sidebar,
                    bottom: persisted.activeTabs?.bottom ?? currentState.activeTabs.bottom,
                };
                const mergedActiveTabs = normalizeActiveTabs(mergedPanels, persistedActiveTabs);
                const mergedMountedTabs = normalizeMountedTabs(
                    mergedPanels,
                    mergedActiveTabs,
                    currentState.mountedTabs ?? DEFAULT_MOUNTED_TABS
                );

                return {
                    ...currentState,
                    panels: mergedPanels,
                    activeTabs: mergedActiveTabs,
                    mountedTabs: mergedMountedTabs,
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
    // Only rely on the reactive store flag here. `persist.hasHydrated()` can
    // already be true on the client's first render, which makes the client
    // render the draggable tab DOM while the server still rendered the
    // placeholder skeleton, causing hydration mismatches.
    return useTabLayoutStore((state) => state._hasHydrated);
}

export function findTabPanel(panels: TabLayoutState["panels"], tabId: TabId): PanelId | null {
    if (panels.sidebar.includes(tabId)) return "sidebar";
    if (panels.bottom.includes(tabId)) return "bottom";
    return null;
}

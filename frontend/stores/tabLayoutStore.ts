"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type TabId =
    | "subtitles"
    | "explanations"
    | "timeline"
    | "ask"
    | "notes"
    | "flashcard"
    | "test"
    | "report"
    | "cheatsheet"
    | "podcast";

export type PanelId = "sidebar" | "bottom";

interface TabLayoutState {
    panels: {
        sidebar: TabId[];
        bottom: TabId[];
    };
    activeTabs: {
        sidebar: TabId;
        bottom: TabId;
    };
    // Actions
    moveTab: (tabId: TabId, sourcePanel: PanelId, targetPanel: PanelId, newIndex: number) => void;
    reorderTab: (panel: PanelId, oldIndex: number, newIndex: number) => void;
    setActiveTab: (panel: PanelId, tabId: TabId) => void;
    resetLayout: () => void;
}

const DEFAULT_SIDEBAR_TABS: TabId[] = ["subtitles", "explanations", "timeline", "ask"];
const DEFAULT_BOTTOM_TABS: TabId[] = ["notes", "flashcard", "test", "report", "cheatsheet", "podcast"];

const MAX_SIDEBAR_TABS = 4;
const MAX_BOTTOM_TABS = 7;

export const useTabLayoutStore = create<TabLayoutState>()(
    persist(
        (set, get) => ({
            panels: {
                sidebar: DEFAULT_SIDEBAR_TABS,
                bottom: DEFAULT_BOTTOM_TABS,
            },
            activeTabs: {
                sidebar: "subtitles",
                bottom: "notes",
            },
            moveTab: (tabId, sourcePanel, targetPanel, newIndex) => {
                const { panels, activeTabs } = get();

                // If moving within same panel, use reorderTab instead
                if (sourcePanel === targetPanel) {
                    const list = panels[sourcePanel];
                    const oldIndex = list.indexOf(tabId);
                    if (oldIndex !== -1) {
                        get().reorderTab(sourcePanel, oldIndex, newIndex);
                    }
                    return;
                }

                // Cross-panel move: check constraints
                const maxTarget = targetPanel === "sidebar" ? MAX_SIDEBAR_TABS : MAX_BOTTOM_TABS;
                if (panels[targetPanel].length >= maxTarget) {
                    return; // Target panel is full
                }

                const sourceList = [...panels[sourcePanel]];
                const targetList = [...panels[targetPanel]];

                const oldIndex = sourceList.indexOf(tabId);
                if (oldIndex === -1) return;

                // Remove from source
                sourceList.splice(oldIndex, 1);

                // Insert into target
                const safeIndex = Math.min(newIndex, targetList.length);
                targetList.splice(safeIndex, 0, tabId);

                // Update active tabs
                const newActiveTabs = { ...activeTabs };

                // If we moved the active tab away, select the first in source
                if (activeTabs[sourcePanel] === tabId && sourceList.length > 0) {
                    newActiveTabs[sourcePanel] = sourceList[0];
                }

                // Make the moved tab active in target
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
                // 允许把标签拖到最末尾；超过范围统一按 append 处理
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
                // Only set if tab exists in that panel
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
                        bottom: "notes",
                    },
                });
            },
        }),
        {
            name: "course-subtitle-tab-layout",
        }
    )
);

// Helper to find which panel a tab belongs to
export function findTabPanel(panels: TabLayoutState["panels"], tabId: TabId): PanelId | null {
    if (panels.sidebar.includes(tabId)) return "sidebar";
    if (panels.bottom.includes(tabId)) return "bottom";
    return null;
}

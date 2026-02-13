"use client";

import { useCallback } from "react";
import dynamic from "next/dynamic";
import { Save, Maximize2, Loader2 } from "lucide-react";
import { useTabLayoutStore, useTabLayoutHydrated, LAYOUT_CONSTRAINTS, type TabId } from "@/stores/tabLayoutStore";
import { DraggableTabBar } from "@/components/dnd/DraggableTabBar";
import type { CrepeEditor } from "@/components/editor/MarkdownNoteEditor";
import { renderTabContent, type TabContentProps } from "./TabContentRenderer";

// Only the notes editor needs special handling in this component
const MarkdownNoteEditor = dynamic(
    () => import("@/components/editor/MarkdownNoteEditor").then((mod) => mod.MarkdownNoteEditor),
    {
        loading: () => (
            <div className="flex h-full items-center justify-center text-gray-500">
                <Loader2 className="w-5 h-5 animate-spin mr-2" />
                <span className="text-sm">Loading...</span>
            </div>
        ),
    }
);

/**
 * Props for NotesPanel - extends TabContentProps (ISP-compliant grouped interfaces)
 * Only adds notes-specific prop: onEditorReady
 */
export interface NotesPanelProps extends TabContentProps {
    onEditorReady: (editor: CrepeEditor) => void;
}

export function NotesPanel({
    videoId,
    onEditorReady,
    ...tabContentProps
}: NotesPanelProps) {
    const isHydrated = useTabLayoutHydrated();
    const tabs = useTabLayoutStore((state) => state.panels.bottom);
    const activeTab = useTabLayoutStore((state) => state.activeTabs.bottom);
    const setActiveTab = useTabLayoutStore((state) => state.setActiveTab);

    const handleTabClick = (id: TabId) => {
        setActiveTab("bottom", id);
    };

    const handleToggleFullscreen = useCallback(() => {
        const editor = document.querySelector(".markdown-note-editor-container");
        if (editor) {
            if (document.fullscreenElement) {
                document.exitFullscreen();
            } else {
                editor.requestFullscreen();
            }
        }
    }, []);

    // Wait for hydration before rendering to prevent tab order flash
    if (!isHydrated) {
        return (
            <div className="flex-1 min-h-0 flex flex-col bg-card dark:bg-[#20293a] rounded-xl border border-border shadow-sm overflow-hidden">
                <div className="flex border-b border-border px-1 items-center min-h-[44px]">
                    <div className="flex gap-2 px-2">
                        {[1, 2, 3, 4, 5].map((i) => (
                            <div key={i} className="h-5 w-16 bg-muted animate-pulse rounded" />
                        ))}
                    </div>
                </div>
                <div className="flex-1 flex items-center justify-center">
                    <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                </div>
            </div>
        );
    }

    // Notes tab has special rendering (includes the editor)
    const renderContent = (tabId: TabId) => {
        if (tabId === "notes") {
            return (
                <div className="h-full relative markdown-note-editor-container">
                    <MarkdownNoteEditor videoId={videoId} onEditorReady={onEditorReady} />
                </div>
            );
        }
        // All other tabs use shared renderer - reconstruct full TabContentProps
        return renderTabContent(tabId, { videoId, ...tabContentProps });
    };

    const extraActions =
        activeTab === "notes" ? (
            <div className="flex items-center gap-3 pr-2">
                <span className="text-xs text-muted-foreground flex items-center gap-1 whitespace-nowrap">
                    <Save className="w-3 h-3" />
                    Auto-saved
                </span>
                <button
                    onClick={handleToggleFullscreen}
                    className="p-1.5 hover:bg-muted rounded-md transition-colors"
                    title="Toggle fullscreen"
                >
                    <Maximize2 className="w-4 h-4 text-muted-foreground" />
                </button>
            </div>
        ) : null;

    // If no tabs in bottom panel, show empty state
    if (tabs.length === 0) {
        return (
            <div className="flex-1 min-h-0 flex flex-col bg-card dark:bg-[#20293a] rounded-xl border border-border shadow-sm overflow-hidden">
                <DraggableTabBar
                    panelId="bottom"
                    tabs={tabs}
                    activeTab={activeTab}
                    onTabClick={handleTabClick}
                    maxTabs={LAYOUT_CONSTRAINTS.MAX_BOTTOM_TABS}
                />
                <div className="flex-1 flex items-center justify-center text-muted-foreground p-8">
                    <p className="text-sm">Drop tabs here</p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex-1 min-h-0 flex flex-col bg-card dark:bg-[#20293a] rounded-xl border border-border shadow-sm overflow-hidden">
            <DraggableTabBar
                panelId="bottom"
                tabs={tabs}
                activeTab={activeTab}
                onTabClick={handleTabClick}
                maxTabs={LAYOUT_CONSTRAINTS.MAX_BOTTOM_TABS}
                extraActions={extraActions}
            />
            <div className="flex-1 min-h-0 relative">{renderContent(activeTab)}</div>
        </div>
    );
}

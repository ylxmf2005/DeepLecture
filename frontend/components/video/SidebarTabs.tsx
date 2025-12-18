"use client";

import { Loader2 } from "lucide-react";
import { useTabLayoutStore, useTabLayoutHydrated, type TabId } from "@/stores/tabLayoutStore";
import { DraggableTabBar } from "@/components/dnd/DraggableTabBar";
import { renderTabContent, type TabContentProps } from "./TabContentRenderer";

/**
 * Props for SidebarTabs - directly uses TabContentProps (ISP-compliant grouped interfaces)
 * No sidebar-specific props needed
 */
export type SidebarTabsProps = TabContentProps;

export function SidebarTabs(props: SidebarTabsProps) {
    const isHydrated = useTabLayoutHydrated();
    const tabs = useTabLayoutStore((state) => state.panels.sidebar);
    const activeTab = useTabLayoutStore((state) => state.activeTabs.sidebar);
    const setActiveTab = useTabLayoutStore((state) => state.setActiveTab);

    const handleTabClick = (id: TabId) => {
        setActiveTab("sidebar", id);
    };

    // Wait for hydration before rendering to prevent tab order flash
    if (!isHydrated) {
        return (
            <div className="flex flex-col bg-card rounded-xl border border-border shadow-sm overflow-hidden min-h-0">
                <div className="flex border-b border-border px-1 items-center min-h-[44px]">
                    <div className="flex gap-2 px-2">
                        {[1, 2, 3, 4].map((i) => (
                            <div key={i} className="h-5 w-16 bg-muted animate-pulse rounded" />
                        ))}
                    </div>
                </div>
                <div className="flex-1 flex items-center justify-center p-8">
                    <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                </div>
            </div>
        );
    }

    // If no tabs in sidebar, show empty state
    if (tabs.length === 0) {
        return (
            <div className="flex flex-col bg-card rounded-xl border border-border shadow-sm overflow-hidden min-h-0">
                <DraggableTabBar
                    panelId="sidebar"
                    tabs={tabs}
                    activeTab={activeTab}
                    onTabClick={handleTabClick}
                    maxTabs={4}
                />
                <div className="flex-1 flex items-center justify-center text-muted-foreground p-8">
                    <p className="text-sm">Drop tabs here</p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col bg-card rounded-xl border border-border shadow-sm overflow-hidden min-h-0">
            <DraggableTabBar
                panelId="sidebar"
                tabs={tabs}
                activeTab={activeTab}
                onTabClick={handleTabClick}
                maxTabs={4}
            />

            <div className="flex-1 overflow-hidden relative min-h-0">
                {renderTabContent(activeTab, props)}
            </div>
        </div>
    );
}

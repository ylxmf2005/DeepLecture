"use client";

import React from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useDroppable } from "@dnd-kit/core";
import { SortableContext, horizontalListSortingStrategy } from "@dnd-kit/sortable";
import { cn } from "@/lib/utils";
import {
    FileText,
    BookOpen,
    LayoutList,
    MessageSquare,
    StickyNote,
    CreditCard,
    CheckSquare,
    FileBarChart,
    ScrollText,
    Mic,
} from "lucide-react";
import type { TabId, PanelId } from "@/stores/tabLayoutStore";

// Configuration for Tab appearance
export const TAB_CONFIG: Record<TabId, { label: string; icon: React.ReactNode }> = {
    subtitles: { label: "Subtitles", icon: <FileText className="w-4 h-4" /> },
    explanations: { label: "Explain", icon: <BookOpen className="w-4 h-4" /> },
    timeline: { label: "Timeline", icon: <LayoutList className="w-4 h-4" /> },
    ask: { label: "Ask", icon: <MessageSquare className="w-4 h-4" /> },
    notes: { label: "Notes", icon: <StickyNote className="w-4 h-4" /> },
    flashcard: { label: "Flashcard", icon: <CreditCard className="w-4 h-4" /> },
    test: { label: "Test", icon: <CheckSquare className="w-4 h-4" /> },
    report: { label: "Report", icon: <FileBarChart className="w-4 h-4" /> },
    cheatsheet: { label: "Cheatsheet", icon: <ScrollText className="w-4 h-4" /> },
    podcast: { label: "Podcast", icon: <Mic className="w-4 h-4" /> },
};

interface SortableTabProps {
    id: TabId;
    active: boolean;
    onClick: () => void;
}

function SortableTab({ id, active, onClick }: SortableTabProps) {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging,
    } = useSortable({ id });

    const style: React.CSSProperties = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.4 : 1,
        zIndex: isDragging ? 50 : "auto",
    };

    const config = TAB_CONFIG[id];

    return (
        <button
            ref={setNodeRef}
            style={style}
            {...attributes}
            {...listeners}
            onClick={onClick}
            className={cn(
                "px-3 py-2 text-sm font-medium border-b-2 transition-all duration-200 flex items-center justify-center gap-1.5 whitespace-nowrap flex-shrink-0",
                "cursor-grab active:cursor-grabbing select-none",
                "hover:bg-accent/50",
                active
                    ? "border-blue-500 text-blue-600 dark:text-blue-400"
                    : "border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300",
                isDragging && "shadow-lg ring-2 ring-primary/20 rounded-md bg-popover"
            )}
        >
            {config.icon}
            <span className="hidden sm:inline">{config.label}</span>
        </button>
    );
}

interface DraggableTabBarProps {
    panelId: PanelId;
    tabs: TabId[];
    activeTab: TabId;
    onTabClick: (id: TabId) => void;
    maxTabs: number;
    extraActions?: React.ReactNode;
}

export function DraggableTabBar({
    panelId,
    tabs,
    activeTab,
    onTabClick,
    maxTabs,
    extraActions,
}: DraggableTabBarProps) {
    const { setNodeRef, isOver } = useDroppable({
        id: panelId,
        data: { type: "panel", panelId },
    });

    const isFull = tabs.length >= maxTabs;

    return (
        <div
            ref={setNodeRef}
            className={cn(
                "flex border-b border-border px-1 items-center overflow-x-auto no-scrollbar min-h-[44px]",
                "transition-colors duration-200",
                isOver && !isFull && "bg-primary/5 ring-2 ring-inset ring-primary/30",
                isOver && isFull && "bg-destructive/5 ring-2 ring-inset ring-destructive/30"
            )}
        >
            <SortableContext items={tabs} strategy={horizontalListSortingStrategy}>
                {tabs.map((tabId) => (
                    <SortableTab
                        key={tabId}
                        id={tabId}
                        active={activeTab === tabId}
                        onClick={() => onTabClick(tabId)}
                    />
                ))}
            </SortableContext>

            {/* Empty state placeholder */}
            {tabs.length === 0 && (
                <div className="flex-1 flex items-center justify-center text-xs text-muted-foreground py-2">
                    Drop tabs here
                </div>
            )}

            <div className="flex-1" />

            {/* Capacity indicator when dragging */}
            {isOver && (
                <span
                    className={cn(
                        "text-xs px-2 py-0.5 rounded-full mr-2",
                        isFull
                            ? "bg-destructive/10 text-destructive"
                            : "bg-primary/10 text-primary"
                    )}
                >
                    {tabs.length}/{maxTabs}
                </span>
            )}

            {extraActions}
        </div>
    );
}

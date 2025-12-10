"use client";

import dynamic from "next/dynamic";
import { SubtitleList } from "@/components/SubtitleList";
import { ContentItem, TimelineEntry } from "@/lib/api";
import type { ProcessingAction } from "@/hooks/useVideoPageState";
import { Subtitle } from "@/lib/srt";
import type { AskContextItem } from "@/lib/askTypes";
import { cn } from "@/lib/utils";
import { FileText, BookOpen, LayoutList, Loader2 } from "lucide-react";
import type { SubtitleMode } from "@/hooks/useSubtitleManagement";
import { useTabLayoutStore, type TabId } from "@/stores/tabLayoutStore";
import { DraggableTabBar } from "@/components/dnd/DraggableTabBar";

// Lazy load components that use MarkdownRenderer (KaTeX)
const ExplanationList = dynamic(
    () => import("@/components/ExplanationList").then((mod) => mod.ExplanationList),
    {
        loading: () => (
            <div className="flex h-full items-center justify-center text-gray-500">
                <Loader2 className="w-5 h-5 animate-spin mr-2" />
                <span className="text-sm">Loading...</span>
            </div>
        ),
    }
);

const AskTab = dynamic(
    () => import("@/components/AskTab").then((mod) => mod.AskTab),
    {
        loading: () => (
            <div className="flex h-full items-center justify-center text-gray-500">
                <Loader2 className="w-5 h-5 animate-spin mr-2" />
                <span className="text-sm">Loading...</span>
            </div>
        ),
    }
);

const TimelineList = dynamic(
    () => import("@/components/TimelineList").then((mod) => mod.TimelineList),
    {
        loading: () => (
            <div className="flex h-full items-center justify-center text-gray-500">
                <Loader2 className="w-5 h-5 animate-spin mr-2" />
                <span className="text-sm">Loading...</span>
            </div>
        ),
    }
);

export interface SidebarTabsProps {
    content: ContentItem;
    videoId: string;
    currentTime: number;
    // Subtitle props
    sidebarSubtitleMode: SubtitleMode;
    setSidebarSubtitleMode: (mode: SubtitleMode) => void;
    sidebarSubtitles: Subtitle[];
    subtitlesZh: Subtitle[];
    subtitlesEnZh: Subtitle[];
    subtitlesZhEn: Subtitle[];
    subtitlesLoading: boolean;
    // Processing props
    processing: boolean;
    processingAction: ProcessingAction;
    // Timeline props
    timelineEntries: TimelineEntry[];
    timelineLoading: boolean;
    // Explanation props
    refreshExplanations: number;
    // Ask props
    askContext: AskContextItem[];
    learnerProfile: string | null;
    subtitleContextWindowSeconds: number;
    // Handlers
    onSeek: (time: number) => void;
    onAddToAsk: (item: AskContextItem) => void;
    onAddToNotes: (markdown: string) => void;
    onRemoveFromAsk: (id: string) => void;
    onGenerateSubtitles: () => void;
    onGenerateTimeline: () => void;
}

export function SidebarTabs({
    content,
    videoId,
    currentTime,
    sidebarSubtitleMode,
    setSidebarSubtitleMode,
    sidebarSubtitles,
    subtitlesZh,
    subtitlesEnZh,
    subtitlesZhEn,
    subtitlesLoading,
    processing,
    processingAction,
    timelineEntries,
    timelineLoading,
    refreshExplanations,
    askContext,
    learnerProfile,
    subtitleContextWindowSeconds,
    onSeek,
    onAddToAsk,
    onAddToNotes,
    onRemoveFromAsk,
    onGenerateSubtitles,
    onGenerateTimeline,
}: SidebarTabsProps) {
    const tabs = useTabLayoutStore((state) => state.panels.sidebar);
    const activeTab = useTabLayoutStore((state) => state.activeTabs.sidebar);
    const setActiveTab = useTabLayoutStore((state) => state.setActiveTab);

    const handleTabClick = (id: TabId) => {
        setActiveTab("sidebar", id);
    };

    const renderNoVideoPlaceholder = (icon: React.ReactNode, message: string) => (
        <div className="flex items-center justify-center h-full p-8 text-center">
            <div className="max-w-md space-y-4">
                {icon}
                <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">
                    No Video Yet
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                    {message}
                </p>
            </div>
        </div>
    );

    const renderPlaceholder = (label: string) => (
        <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
                <FileText className="w-16 h-16 mx-auto mb-4 opacity-20" />
                <p className="text-sm">{label} feature coming soon...</p>
            </div>
        </div>
    );

    const renderContent = (tabId: TabId) => {
        switch (tabId) {
            case "subtitles":
                if (content.type === "slide" && content.videoStatus !== "ready") {
                    return renderNoVideoPlaceholder(
                        <FileText className="w-12 h-12 mx-auto text-gray-400" />,
                        "Subtitles are available after generating the lecture video from your slide deck."
                    );
                }
                if (content.subtitleStatus !== "ready") {
                    return (
                        <div className="flex flex-col items-center justify-center h-full text-gray-500 gap-4 p-8 text-center">
                            <FileText className="w-12 h-12 opacity-20" />
                            <p>No subtitles generated yet.</p>
                            <button
                                onClick={onGenerateSubtitles}
                                disabled={processing}
                                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                            >
                                {processing && processingAction === "generate" ? "Generating..." : "Generate Subtitles"}
                            </button>
                        </div>
                    );
                }
                return (
                    <div className="flex flex-col h-full min-h-0">
                        <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-muted/30">
                            <span className="text-xs text-gray-500 dark:text-gray-400">
                                Subtitle view
                            </span>
                            <div className="inline-flex rounded-md border border-border bg-muted overflow-hidden">
                                <button
                                    onClick={() => setSidebarSubtitleMode("en")}
                                    className={cn(
                                        "px-2 py-1 text-xs transition-colors",
                                        sidebarSubtitleMode === "en"
                                            ? "bg-blue-600 text-white"
                                            : "text-foreground hover:bg-muted-foreground/10"
                                    )}
                                >
                                    EN
                                </button>
                                <button
                                    onClick={() => setSidebarSubtitleMode("zh")}
                                    disabled={subtitlesZh.length === 0}
                                    className={cn(
                                        "px-2 py-1 text-xs border-l border-border transition-colors",
                                        sidebarSubtitleMode === "zh"
                                            ? "bg-blue-600 text-white"
                                            : "text-foreground hover:bg-muted-foreground/10",
                                        subtitlesZh.length === 0 && "opacity-50 cursor-not-allowed"
                                    )}
                                >
                                    ZH
                                </button>
                                <button
                                    onClick={() => setSidebarSubtitleMode("en_zh")}
                                    disabled={subtitlesEnZh.length === 0}
                                    className={cn(
                                        "px-2 py-1 text-xs border-l border-border transition-colors",
                                        sidebarSubtitleMode === "en_zh"
                                            ? "bg-blue-600 text-white"
                                            : "text-foreground hover:bg-muted-foreground/10",
                                        subtitlesEnZh.length === 0 && "opacity-50 cursor-not-allowed"
                                    )}
                                >
                                    EN+ZH
                                </button>
                                <button
                                    onClick={() => setSidebarSubtitleMode("zh_en")}
                                    disabled={subtitlesZhEn.length === 0}
                                    className={cn(
                                        "px-2 py-1 text-xs border-l border-border transition-colors",
                                        sidebarSubtitleMode === "zh_en"
                                            ? "bg-blue-600 text-white"
                                            : "text-foreground hover:bg-muted-foreground/10",
                                        subtitlesZhEn.length === 0 && "opacity-50 cursor-not-allowed"
                                    )}
                                >
                                    ZH+EN
                                </button>
                            </div>
                        </div>

                        <div className="flex-1 min-h-0">
                            {subtitlesLoading && sidebarSubtitles.length === 0 ? (
                                <div className="flex h-full items-center justify-center text-gray-500">
                                    <Loader2 className="w-5 h-5 animate-spin mr-2" />
                                    <span className="text-sm">Loading subtitles...</span>
                                </div>
                            ) : sidebarSubtitles.length > 0 ? (
                                <SubtitleList
                                    subtitles={sidebarSubtitles}
                                    currentTime={currentTime}
                                    onSeek={onSeek}
                                    onAddToAsk={onAddToAsk}
                                    onAddToNotes={onAddToNotes}
                                />
                            ) : (
                                <div className="flex flex-col items-center justify-center h-full text-gray-500 gap-4 p-8 text-center">
                                    <FileText className="w-12 h-12 opacity-20" />
                                    <p>No subtitles available. Try generating them in the Actions tab.</p>
                                </div>
                            )}
                        </div>
                    </div>
                );

            case "explanations":
                if (content.type === "slide" && content.videoStatus !== "ready") {
                    return renderNoVideoPlaceholder(
                        <BookOpen className="w-12 h-12 mx-auto text-gray-400" />,
                        "Screenshots are available after generating the lecture video from your slide deck."
                    );
                }
                return (
                    <ExplanationList
                        videoId={videoId}
                        refreshTrigger={refreshExplanations}
                        onSeek={onSeek}
                        onAddToAsk={onAddToAsk}
                        onAddToNotes={onAddToNotes}
                    />
                );

            case "ask":
                return (
                    <AskTab
                        context={askContext}
                        onRemoveContext={onRemoveFromAsk}
                        videoId={videoId}
                        learnerProfile={learnerProfile || undefined}
                        subtitleContextWindowSeconds={subtitleContextWindowSeconds}
                        onAddToNotes={onAddToNotes}
                    />
                );

            case "timeline":
                if (content.type === "slide" && content.videoStatus !== "ready") {
                    return renderNoVideoPlaceholder(
                        <LayoutList className="w-12 h-12 mx-auto text-gray-400" />,
                        "Timeline is available after generating the lecture video from your slide deck."
                    );
                }
                return (
                    <TimelineList
                        entries={timelineEntries}
                        onSeek={onSeek}
                        currentTime={currentTime}
                        onAddToAsk={onAddToAsk}
                        onAddToNotes={onAddToNotes}
                        onGenerate={onGenerateTimeline}
                        isGenerating={timelineLoading}
                    />
                );

            // Tabs that might be moved from bottom panel
            case "notes":
            case "flashcard":
            case "test":
            case "report":
            case "cheatsheet":
            case "podcast":
                return renderPlaceholder(tabId.charAt(0).toUpperCase() + tabId.slice(1));

            default:
                return null;
        }
    };

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
                {renderContent(activeTab)}
            </div>
        </div>
    );
}

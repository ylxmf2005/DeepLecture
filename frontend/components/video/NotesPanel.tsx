"use client";

import { useCallback } from "react";
import dynamic from "next/dynamic";
import { cn } from "@/lib/utils";
import { FileText, Save, Maximize2, Loader2, BookOpen, LayoutList } from "lucide-react";
import { useTabLayoutStore, type TabId } from "@/stores/tabLayoutStore";
import { DraggableTabBar } from "@/components/dnd/DraggableTabBar";
import type { MarkdownNoteEditor as MarkdownNoteEditorType, CrepeEditor } from "@/components/MarkdownNoteEditor";
import type { ContentItem, TimelineEntry } from "@/lib/api";
import type { Subtitle } from "@/lib/srt";
import type { AskContextItem } from "@/lib/askTypes";
import type { SubtitleMode } from "@/hooks/useSubtitleManagement";
import type { ProcessingAction } from "@/hooks/useVideoPageState";
import { SubtitleList } from "@/components/SubtitleList";

// Dynamic Imports
const MarkdownNoteEditor = dynamic(
    () => import("@/components/MarkdownNoteEditor").then((mod) => mod.MarkdownNoteEditor),
    {
        loading: () => (
            <div className="flex h-full items-center justify-center text-gray-500">
                <Loader2 className="w-5 h-5 animate-spin mr-2" />
                <span className="text-sm">Loading...</span>
            </div>
        ),
    }
);

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

export interface NotesPanelProps {
    videoId: string;
    onEditorReady: (editor: CrepeEditor) => void;
    // Additional props needed for tabs that might be moved here
    content: ContentItem;
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

export function NotesPanel({
    videoId,
    onEditorReady,
    content,
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
}: NotesPanelProps) {
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

    const renderPlaceholderTab = (label: string) => (
        <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
                <FileText className="w-16 h-16 mx-auto mb-4 opacity-20" />
                <p className="text-sm">{label} feature coming soon...</p>
            </div>
        </div>
    );

    const renderContent = (tabId: TabId) => {
        switch (tabId) {
            case "notes":
                return (
                    <div className="h-full relative markdown-note-editor-container">
                        <MarkdownNoteEditor videoId={videoId} onEditorReady={onEditorReady} />
                    </div>
                );

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
                            <span className="text-xs text-gray-500 dark:text-gray-400">Subtitle view</span>
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
                            ) : (
                                <SubtitleList
                                    subtitles={sidebarSubtitles}
                                    currentTime={currentTime}
                                    onSeek={onSeek}
                                    onAddToAsk={onAddToAsk}
                                    onAddToNotes={onAddToNotes}
                                />
                            )}
                        </div>
                    </div>
                );

            case "explanations":
                if (content.type === "slide" && content.videoStatus !== "ready") {
                    return renderNoVideoPlaceholder(
                        <BookOpen className="w-12 h-12 mx-auto text-gray-400" />,
                        "Screenshots available after generation."
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

            case "timeline":
                if (content.type === "slide" && content.videoStatus !== "ready") {
                    return renderNoVideoPlaceholder(
                        <LayoutList className="w-12 h-12 mx-auto text-gray-400" />,
                        "Timeline available after generation."
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

            case "flashcard":
            case "test":
            case "report":
            case "cheatsheet":
            case "podcast":
                return renderPlaceholderTab(tabId.charAt(0).toUpperCase() + tabId.slice(1));

            default:
                return null;
        }
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
            <div className="flex-1 h-full min-h-0 flex flex-col bg-card dark:bg-[#20293a] rounded-xl border border-border shadow-sm overflow-hidden">
                <DraggableTabBar
                    panelId="bottom"
                    tabs={tabs}
                    activeTab={activeTab}
                    onTabClick={handleTabClick}
                    maxTabs={7}
                />
                <div className="flex-1 flex items-center justify-center text-muted-foreground p-8">
                    <p className="text-sm">Drop tabs here</p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex-1 h-full min-h-0 flex flex-col bg-card dark:bg-[#20293a] rounded-xl border border-border shadow-sm overflow-hidden">
            <DraggableTabBar
                panelId="bottom"
                tabs={tabs}
                activeTab={activeTab}
                onTabClick={handleTabClick}
                maxTabs={7}
                extraActions={extraActions}
            />
            <div className="flex-1 min-h-0 relative">{renderContent(activeTab)}</div>
        </div>
    );
}

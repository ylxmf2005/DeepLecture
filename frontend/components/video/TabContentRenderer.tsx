"use client";

import { memo } from "react";
import dynamic from "next/dynamic";
import { cn } from "@/lib/utils";
import { FileText, BookOpen, LayoutList, Loader2 } from "lucide-react";
import type { TabId } from "@/stores/tabLayoutStore";
import type { ContentItem, TimelineEntry } from "@/lib/api";
import type { Subtitle } from "@/lib/srt";
import type { AskContextItem } from "@/lib/askTypes";
import type { SubtitleDisplayMode } from "@/stores/types";
import type { ProcessingAction } from "@/hooks/useVideoPageState";
import { SubtitleList } from "@/components/content/SubtitleList";

// Shared loading component for dynamic imports
const LoadingSpinner = () => (
    <div className="flex h-full items-center justify-center text-gray-500">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        <span className="text-sm">Loading...</span>
    </div>
);

// Dynamic Imports - shared across both panels
const ExplanationList = dynamic(
    () => import("@/components/content/ExplanationList").then((mod) => mod.ExplanationList),
    { loading: LoadingSpinner }
);

const AskTab = dynamic(
    () => import("@/components/features/AskTab").then((mod) => mod.AskTab),
    { loading: LoadingSpinner }
);

const TimelineList = dynamic(
    () => import("@/components/content/TimelineList").then((mod) => mod.TimelineList),
    { loading: LoadingSpinner }
);

const VerifyTab = dynamic(
    () => import("@/components/features/VerifyTab").then((mod) => mod.VerifyTab),
    { loading: LoadingSpinner }
);

// Grouped prop interfaces for better organization (ISP)

/** Subtitle-related props for the sidebar subtitle panel */
export interface SubtitleProps {
    sidebarSubtitleMode: SubtitleDisplayMode;
    setSidebarSubtitleMode: (mode: SubtitleDisplayMode) => void;
    sidebarSubtitles: Subtitle[];
    subtitlesTarget: Subtitle[];
    subtitlesDual: Subtitle[];
    subtitlesDualReversed: Subtitle[];
    subtitlesLoading: boolean;
}

/** Processing state for async operations */
export interface ProcessingProps {
    processing: boolean;
    processingAction: ProcessingAction;
}

/** Timeline-related props */
export interface TimelineProps {
    timelineEntries: TimelineEntry[];
    timelineLoading: boolean;
}

/** Ask AI tab props */
export interface AskProps {
    askContext: AskContextItem[];
    learnerProfile: string | null;
    subtitleContextWindowSeconds: number;
}

/** Event handlers for tab content interactions */
export interface TabContentHandlers {
    onSeek: (time: number) => void;
    onAddToAsk: (item: AskContextItem) => void;
    onAddToNotes: (markdown: string) => void;
    onRemoveFromAsk: (id: string) => void;
    onGenerateSubtitles: () => void;
    onGenerateTimeline: () => void;
}

/** Complete props for TabContentRenderer using composition */
export interface TabContentProps extends SubtitleProps, ProcessingProps, TimelineProps, AskProps, TabContentHandlers {
    videoId: string;
    content: ContentItem;
    currentTime: number;
    refreshExplanations: number;
    refreshVerification: number;
}

// Shared placeholder for "no video yet" state
export const NoVideoPlaceholder = memo(function NoVideoPlaceholder({ icon, message }: { icon: React.ReactNode; message: string }) {
    return (
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
});

// Shared placeholder for coming soon features
export const FeaturePlaceholder = memo(function FeaturePlaceholder({ label }: { label: string }) {
    return (
        <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
                <FileText className="w-16 h-16 mx-auto mb-4 opacity-20" />
                <p className="text-sm">{label} feature coming soon...</p>
            </div>
        </div>
    );
});

// Subtitle mode toggle buttons - semantic UI component
function SubtitleModeToggle({
    sidebarSubtitleMode,
    setSidebarSubtitleMode,
    subtitlesTarget,
    subtitlesDual,
    subtitlesDualReversed,
}: Pick<SubtitleProps, "sidebarSubtitleMode" | "setSidebarSubtitleMode" | "subtitlesTarget" | "subtitlesDual" | "subtitlesDualReversed">) {
    return (
        <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-muted/30">
            <span className="text-xs text-gray-500 dark:text-gray-400">Subtitle view</span>
            <div className="inline-flex rounded-md border border-border bg-muted overflow-hidden">
                <button
                    onClick={() => setSidebarSubtitleMode("source")}
                    className={cn(
                        "px-2 py-1 text-xs transition-colors",
                        sidebarSubtitleMode === "source"
                            ? "bg-blue-600 text-white"
                            : "text-foreground hover:bg-muted-foreground/10"
                    )}
                >
                    Source
                </button>
                <button
                    onClick={() => setSidebarSubtitleMode("target")}
                    disabled={subtitlesTarget.length === 0}
                    className={cn(
                        "px-2 py-1 text-xs border-l border-border transition-colors",
                        sidebarSubtitleMode === "target"
                            ? "bg-blue-600 text-white"
                            : "text-foreground hover:bg-muted-foreground/10",
                        subtitlesTarget.length === 0 && "opacity-50 cursor-not-allowed"
                    )}
                >
                    Target
                </button>
                <button
                    onClick={() => setSidebarSubtitleMode("dual")}
                    disabled={subtitlesDual.length === 0}
                    className={cn(
                        "px-2 py-1 text-xs border-l border-border transition-colors",
                        sidebarSubtitleMode === "dual"
                            ? "bg-blue-600 text-white"
                            : "text-foreground hover:bg-muted-foreground/10",
                        subtitlesDual.length === 0 && "opacity-50 cursor-not-allowed"
                    )}
                >
                    Dual
                </button>
                <button
                    onClick={() => setSidebarSubtitleMode("dual_reversed")}
                    disabled={subtitlesDualReversed.length === 0}
                    className={cn(
                        "px-2 py-1 text-xs border-l border-border transition-colors",
                        sidebarSubtitleMode === "dual_reversed"
                            ? "bg-blue-600 text-white"
                            : "text-foreground hover:bg-muted-foreground/10",
                        subtitlesDualReversed.length === 0 && "opacity-50 cursor-not-allowed"
                    )}
                >
                    Dual Rev
                </button>
            </div>
        </div>
    );
}

/**
 * Renders tab content for both sidebar and bottom panels.
 * Single source of truth for tab content rendering logic.
 */
export function renderTabContent(tabId: TabId, props: TabContentProps): React.ReactNode {
    const {
        videoId,
        content,
        currentTime,
        sidebarSubtitleMode,
        setSidebarSubtitleMode,
        sidebarSubtitles,
        subtitlesTarget,
        subtitlesDual,
        subtitlesDualReversed,
        subtitlesLoading,
        processing,
        processingAction,
        timelineEntries,
        timelineLoading,
        refreshExplanations,
        refreshVerification,
        askContext,
        learnerProfile,
        subtitleContextWindowSeconds,
        onSeek,
        onAddToAsk,
        onAddToNotes,
        onRemoveFromAsk,
        onGenerateSubtitles,
        onGenerateTimeline,
    } = props;

    switch (tabId) {
        case "subtitles":
            if (content.type === "slide" && content.videoStatus !== "ready") {
                return (
                    <NoVideoPlaceholder
                        icon={<FileText className="w-12 h-12 mx-auto text-gray-400" />}
                        message="Subtitles are available after generating the lecture video from your slide deck."
                    />
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
                    <SubtitleModeToggle
                        sidebarSubtitleMode={sidebarSubtitleMode}
                        setSidebarSubtitleMode={setSidebarSubtitleMode}
                        subtitlesTarget={subtitlesTarget}
                        subtitlesDual={subtitlesDual}
                        subtitlesDualReversed={subtitlesDualReversed}
                    />
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
                return (
                    <NoVideoPlaceholder
                        icon={<BookOpen className="w-12 h-12 mx-auto text-gray-400" />}
                        message="Screenshots are available after generating the lecture video from your slide deck."
                    />
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
                return (
                    <NoVideoPlaceholder
                        icon={<LayoutList className="w-12 h-12 mx-auto text-gray-400" />}
                        message="Timeline is available after generating the lecture video from your slide deck."
                    />
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
                    onSeek={onSeek}
                />
            );

        case "verify":
            return <VerifyTab videoId={videoId} onSeek={onSeek} refreshTrigger={refreshVerification} />;

        // Placeholder tabs
        case "notes":
        case "flashcard":
        case "test":
        case "report":
        case "cheatsheet":
        case "podcast":
            return <FeaturePlaceholder label={tabId.charAt(0).toUpperCase() + tabId.slice(1)} />;

        default:
            return null;
    }
}

"use client";

import { forwardRef, useState, useRef, useEffect, useMemo } from "react";
import dynamic from "next/dynamic";
import { VideoPlayer, VideoPlayerRef, SubtitlePlayerMode } from "@/components/video/VideoPlayer";
import { ContentItem, API_BASE_URL, SyncTimeline } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
    BookOpen,
    ChevronsLeftRight,
    ChevronsRightLeft,
    FileText,
    Loader2,
    Maximize,
    Maximize2,
    Minimize,
    Minimize2,
} from "lucide-react";
import type { SubtitleDisplayMode, ViewMode } from "@/stores/types";
import { Subtitle } from "@/lib/srt";
import { logger } from "@/shared/infrastructure";

// Dynamically import PdfSlideViewer with SSR disabled to avoid React Compiler
// hook-order mismatches between SSR and client hydration.  The PDF viewer
// requires browser APIs anyway, so skipping SSR is the correct approach.
const PdfSlideViewer = dynamic(() => import("./PdfSlideViewer"), { ssr: false });

const log = logger.scope("VideoPlayerSection");

interface VideoPlayerSectionProps {
    content: ContentItem;
    videoId: string;
    selectedVoiceoverId: string | null;
    selectedVoiceoverSyncTimeline: SyncTimeline | null;
    playerSubtitles: Subtitle[];
    playerSubtitleMode: SubtitleDisplayMode;
    setPlayerSubtitleMode: (mode: SubtitleDisplayMode) => void;
    /** Whether translation is available for quick toggle */
    hasTranslation?: boolean;
    /** Quick toggle preset: Original voiceover ID (null = video original audio) */
    quickToggleOriginalVoiceoverId: string | null;
    /** Quick toggle preset: Translated voiceover ID (null = not set) */
    quickToggleTranslatedVoiceoverId: string | null;
    /** Callback to change the active voiceover */
    onVoiceoverChange: (voiceoverId: string | null) => void;
    generatingVideo: boolean;
    onTimeUpdate: (time: number) => void;
    onCapture: (timestamp: number, imagePath: string) => void;
    onAskAtTime: (time: number) => void;
    onAddNoteAtTime: (time: number) => void;
    onPlayerReady: (videoElement: HTMLVideoElement) => void;
    onGenerateSlideLecture: () => void;
    slideDeck?: {
        id: string;
        name: string;
    } | null;
    onUploadSlide?: (file: File) => void;
    /** Current view mode for layout control */
    viewMode?: ViewMode;
    /** Callback when view mode changes */
    onViewModeChange?: (mode: ViewMode) => void;
    /** Bookmark timestamps to display as dots on the progress bar */
    bookmarkTimestamps?: number[];
    /** Callback when user adds a bookmark (via B key) */
    onAddBookmark?: (time: number) => void;
    /** Optional className for the container */
    className?: string;
}

export const VideoPlayerSection = forwardRef<VideoPlayerRef, VideoPlayerSectionProps>(
    function VideoPlayerSection(
        {
            content,
            videoId,
            selectedVoiceoverId,
            selectedVoiceoverSyncTimeline,
            playerSubtitles,
            playerSubtitleMode,
            setPlayerSubtitleMode,
            hasTranslation,
            quickToggleOriginalVoiceoverId,
            quickToggleTranslatedVoiceoverId,
            onVoiceoverChange,
            generatingVideo,
            onTimeUpdate,
            onCapture,
            onAskAtTime,
            onAddNoteAtTime,
            onPlayerReady,
            onGenerateSlideLecture,
            slideDeck,
            onUploadSlide,
            viewMode,
            onViewModeChange,
            bookmarkTimestamps,
            onAddBookmark,
            className,
        },
        ref
    ) {
        const [playerTab, setPlayerTab] = useState<"player" | "slide">("player");
        const [subtitleModeOverride, setSubtitleModeOverride] = useState<Extract<SubtitlePlayerMode, "off"> | null>(null);
        const subtitleModeUI = useMemo<SubtitlePlayerMode>(
            () => subtitleModeOverride ?? playerSubtitleMode,
            [subtitleModeOverride, playerSubtitleMode]
        );
        const currentViewMode = viewMode ?? "normal";
        const fileRef = useRef<HTMLInputElement | null>(null);
        const slideContainerRef = useRef<HTMLDivElement>(null);
        const [isSlideFullscreen, setIsSlideFullscreen] = useState(false);
        const slidePdfUrl = useMemo(() => {
            if (content.type === "slide") {
                return `${API_BASE_URL}/api/content/${videoId}/pdf`;
            }
            if (slideDeck?.id) {
                return `${API_BASE_URL}/api/content/${slideDeck.id}/pdf`;
            }
            return null;
        }, [content.type, slideDeck?.id, videoId]);
        const hasSlidePdf = !!slidePdfUrl;

        const handleFileClick = () => {
            if (!onUploadSlide) return;
            fileRef.current?.click();
        };

        const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
            if (!onUploadSlide) return;
            const file = event.target.files && event.target.files[0];
            if (!file) return;
            if (file.type !== "application/pdf") return;
            onUploadSlide(file);
        };

        useEffect(() => {
            const handleFullscreenChange = () => {
                setIsSlideFullscreen(!!document.fullscreenElement);
            };

            document.addEventListener("fullscreenchange", handleFullscreenChange);
            return () => {
                document.removeEventListener("fullscreenchange", handleFullscreenChange);
            };
        }, []);

        const toggleSlideFullscreen = async () => {
            if (!slideContainerRef.current) return;

            try {
                if (!document.fullscreenElement) {
                    await slideContainerRef.current.requestFullscreen();
                } else {
                    await document.exitFullscreen();
                }
            } catch (err) {
                log.error("Failed to toggle slide fullscreen", err instanceof Error ? err : new Error(String(err)));
            }
        };

        const renderSlideTab = () => {
            if (slidePdfUrl) {
                return <PdfSlideViewer fileUrl={slidePdfUrl} />;
            }

            if (!onUploadSlide) {
                return (
                    <div className="absolute inset-0 flex items-center justify-center text-gray-500">
                        <div className="text-center">
                            <BookOpen className="w-16 h-16 mx-auto mb-4 opacity-20" />
                            <p className="text-sm">No slide deck available for this video</p>
                        </div>
                    </div>
                );
            }

            return (
                <button
                    type="button"
                    onClick={handleFileClick}
                    className="relative w-full h-full flex items-center justify-center bg-card"
                >
                    <input
                        ref={fileRef}
                        type="file"
                        className="hidden"
                        accept="application/pdf"
                        onChange={handleFileChange}
                    />
                    <div className="text-center p-6 border-2 border-dashed border-border rounded-xl bg-background/60">
                        <FileText className="w-12 h-12 mx-auto mb-4 opacity-20" />
                        <p className="text-sm font-medium mb-1">Upload your slides (PDF)</p>
                        <p className="text-xs text-gray-500">
                            Attach a slide deck for this video. The PDF will be available here; other features come later.
                        </p>
                    </div>
                </button>
            );
        };

        return (
            <div className={cn(
                "relative group overflow-hidden",
                viewMode === "web-fullscreen" ? "w-full h-full" : "shrink-0",
                className
            )}>
                {/* Floating toggle button - only visible when hovering top-left hotspot */}
                <div className="absolute top-4 left-4 z-20 group/tab-toggle p-2 -m-2">
                    <div
                        className={cn(
                            "flex gap-1 bg-black/70 backdrop-blur-sm rounded-lg p-1 shadow-lg transition-opacity duration-200",
                            "opacity-0 pointer-events-none",
                            "group-hover/tab-toggle:opacity-100 group-hover/tab-toggle:pointer-events-auto",
                            "group-focus-within/tab-toggle:opacity-100 group-focus-within/tab-toggle:pointer-events-auto"
                        )}
                    >
                        <button
                            onClick={() => setPlayerTab("player")}
                            className={cn(
                                "px-3 py-1.5 text-xs font-medium rounded-md transition-all",
                                playerTab === "player"
                                    ? "bg-blue-600 text-white"
                                    : "text-white/80 hover:text-white hover:bg-white/10"
                            )}
                        >
                            Player
                        </button>
                        <button
                            onClick={() => setPlayerTab("slide")}
                            className={cn(
                                "px-3 py-1.5 text-xs font-medium rounded-md transition-all",
                                playerTab === "slide"
                                    ? "bg-blue-600 text-white"
                                    : "text-white/80 hover:text-white hover:bg-white/10"
                            )}
                        >
                            Slide
                        </button>
                    </div>
                </div>

                {/* Use visibility:hidden + absolute positioning instead of display:none
                    so the PDF viewer keeps its layout tree alive and preserves scroll position. */}
                <div className={cn(
                    playerTab === "player" ? "" : "invisible absolute inset-0 pointer-events-none",
                    viewMode === "web-fullscreen" && "h-full"
                )}>
                    {content.type === "slide" && (content.videoStatus !== "ready" || generatingVideo) ? (
                        // Slide without video OR regenerating: Show generate/loading state
                        <div className="relative w-full aspect-video bg-card rounded-xl border border-border shadow-sm overflow-hidden flex items-center justify-center">
                            <div className="text-center p-8">
                                <FileText className="w-16 h-16 mx-auto mb-4 opacity-20" />
                                <p className="text-lg font-medium mb-2">PDF Slide Deck</p>
                                <p className="text-sm text-gray-500 mb-4">
                                    {content.filename}
                                    {content.pageCount && ` (${content.pageCount} pages)`}
                                </p>
                                <button
                                    onClick={() => onGenerateSlideLecture()}
                                    disabled={generatingVideo}
                                    className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 mx-auto"
                                >
                                    {generatingVideo && <Loader2 className="w-4 h-4 animate-spin" />}
                                    {generatingVideo
                                        ? (content.videoStatus === "ready" ? "Regenerating Video..." : "Generating Video...")
                                        : (content.videoStatus === "ready" ? "Regenerate Lecture Video" : "Generate Lecture Video")}
                                </button>
                            </div>
                        </div>
                    ) : content.type === "video" && content.videoStatus !== "ready" ? (
                        // Video content still processing (merge in progress)
                        <div className="relative w-full aspect-video bg-card rounded-xl border border-border shadow-sm overflow-hidden flex items-center justify-center">
                            <div className="text-center p-8 max-w-md">
                                <Loader2 className="w-16 h-16 mx-auto mb-4 opacity-40 animate-spin" />
                                <p className="text-lg font-medium mb-2">Processing Video</p>
                                <p className="text-sm text-gray-500 mb-4">
                                    Your video is being processed. This may take a moment...
                                </p>
                            </div>
                        </div>
                    ) : (
                        // Video ready: Show VideoPlayer
                        <VideoPlayer
                            ref={ref}
                            videoId={videoId}
                            title={content.filename}
                            voiceoverId={selectedVoiceoverId}
                            syncTimeline={selectedVoiceoverSyncTimeline}
                            subtitles={playerSubtitles}
                            subtitleMode={subtitleModeUI}
                            onSubtitleModeChange={(mode) => {
                                if (mode === "off") {
                                    setSubtitleModeOverride("off");
                                    return;
                                }
                                setSubtitleModeOverride(null);
                                setPlayerSubtitleMode(mode);
                            }}
                            hasTranslation={hasTranslation}
                            quickToggleOriginalVoiceoverId={quickToggleOriginalVoiceoverId}
                            quickToggleTranslatedVoiceoverId={quickToggleTranslatedVoiceoverId}
                            onVoiceoverChange={onVoiceoverChange}
                            onTimeUpdate={onTimeUpdate}
                            onCapture={onCapture}
                            onAskAtTime={onAskAtTime}
                            onAddNoteAtTime={onAddNoteAtTime}
                            onPlayerReady={onPlayerReady}
                            bookmarkTimestamps={bookmarkTimestamps}
                            onAddBookmark={onAddBookmark}
                            viewMode={viewMode}
                            onViewModeChange={onViewModeChange}
                        />
                    )}
                </div>
                <div
                    ref={slideContainerRef}
                    className={cn(
                        "relative w-full bg-card rounded-xl border border-border shadow-sm overflow-hidden flex items-center justify-center bg-black",
                        currentViewMode === "web-fullscreen" || isSlideFullscreen
                            ? "h-full"
                            : "h-[72vh] min-h-[480px] max-h-[calc(100vh-180px)]",
                        playerTab === "slide" ? "" : "invisible absolute top-0 left-0 w-full pointer-events-none"
                    )}
                >
                    {renderSlideTab()}

                    {/* Slide mode controls */}
                    {playerTab === "slide" && hasSlidePdf && (
                        <div className="absolute bottom-4 right-4 z-20 group/slide-controls p-2 -m-2">
                            <div
                                className={cn(
                                    "flex items-center gap-1 rounded-lg bg-black/60 p-1 backdrop-blur-sm shadow-lg transition-opacity",
                                    "opacity-0 pointer-events-none",
                                    "group-hover/slide-controls:opacity-100 group-hover/slide-controls:pointer-events-auto",
                                    "group-focus-within/slide-controls:opacity-100 group-focus-within/slide-controls:pointer-events-auto"
                                )}
                            >
                                {onViewModeChange && (
                                    <button
                                        onClick={() =>
                                            onViewModeChange(currentViewMode === "widescreen" ? "normal" : "widescreen")
                                        }
                                        className={cn(
                                            "p-2 rounded-md transition-colors",
                                            currentViewMode === "widescreen"
                                                ? "text-blue-400 bg-white/10"
                                                : "text-white hover:text-white/80"
                                        )}
                                        title={currentViewMode === "widescreen" ? "Exit widescreen" : "Widescreen"}
                                    >
                                        {currentViewMode === "widescreen" ? (
                                            <ChevronsRightLeft className="w-4 h-4" />
                                        ) : (
                                            <ChevronsLeftRight className="w-4 h-4" />
                                        )}
                                    </button>
                                )}

                                {onViewModeChange && (
                                    <button
                                        onClick={() =>
                                            onViewModeChange(currentViewMode === "web-fullscreen" ? "normal" : "web-fullscreen")
                                        }
                                        className={cn(
                                            "p-2 rounded-md transition-colors",
                                            currentViewMode === "web-fullscreen"
                                                ? "text-blue-400 bg-white/10"
                                                : "text-white hover:text-white/80"
                                        )}
                                        title={currentViewMode === "web-fullscreen" ? "Exit web fullscreen" : "Web fullscreen"}
                                    >
                                        {currentViewMode === "web-fullscreen" ? (
                                            <Minimize className="w-4 h-4" />
                                        ) : (
                                            <Maximize className="w-4 h-4" />
                                        )}
                                    </button>
                                )}

                                <button
                                    onClick={toggleSlideFullscreen}
                                    className={cn(
                                        "p-2 rounded-md transition-colors",
                                        isSlideFullscreen
                                            ? "text-blue-400 bg-white/10"
                                            : "text-white hover:text-white/80"
                                    )}
                                    title={isSlideFullscreen ? "Exit fullscreen" : "Fullscreen"}
                                >
                                    {isSlideFullscreen ? (
                                        <Minimize2 className="w-4 h-4" />
                                    ) : (
                                        <Maximize2 className="w-4 h-4" />
                                    )}
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        );
    }
);

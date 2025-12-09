"use client";

import { forwardRef, useState, useRef, useEffect } from "react";
import { VideoPlayer, VideoPlayerRef } from "@/components/VideoPlayer";
import { ContentItem, API_BASE_URL } from "@/lib/api";
import { cn } from "@/lib/utils";
import { FileText, BookOpen, Loader2, Maximize, Minimize } from "lucide-react";
import type { PlayerTrack, SubtitleMode } from "@/hooks/useSubtitleManagement";
import { Subtitle } from "@/lib/srt";

interface VideoPlayerSectionProps {
    content: ContentItem;
    videoId: string;
    selectedVoiceoverId: string | null;
    playerTracks: PlayerTrack[];
    playerSubtitles: Subtitle[];
    playerSubtitleMode: SubtitleMode;
    setPlayerSubtitleMode: (mode: SubtitleMode) => void;
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
}

export const VideoPlayerSection = forwardRef<VideoPlayerRef, VideoPlayerSectionProps>(
    function VideoPlayerSection(
        {
            content,
            videoId,
            selectedVoiceoverId,
            playerTracks,
            playerSubtitles,
            playerSubtitleMode,
            setPlayerSubtitleMode,
            generatingVideo,
            onTimeUpdate,
            onCapture,
            onAskAtTime,
            onAddNoteAtTime,
            onPlayerReady,
            onGenerateSlideLecture,
            slideDeck,
            onUploadSlide,
        },
        ref
    ) {
        const [playerTab, setPlayerTab] = useState<"player" | "slide">("player");
        const fileRef = useRef<HTMLInputElement | null>(null);
        const slideContainerRef = useRef<HTMLDivElement>(null);
        const [isSlideFullscreen, setIsSlideFullscreen] = useState(false);

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
                console.error("Error toggling slide fullscreen:", err);
            }
        };

        const renderSlideTab = () => {
            if (content.type === "slide") {
                return (
                    <iframe
                        src={`${API_BASE_URL}/api/content/${videoId}/pdf`}
                        className="w-full h-full"
                        title="PDF Slide Deck"
                    />
                );
            }

            if (slideDeck && slideDeck.id) {
                return (
                    <iframe
                        src={`${API_BASE_URL}/api/content/${slideDeck.id}/pdf`}
                        className="w-full h-full"
                        title="PDF Slide Deck"
                    />
                );
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
            <div className="shrink-0 relative group">
                {/* Floating toggle button - only visible on hover */}
                <div className="absolute top-4 left-4 z-20 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                    <div className="flex gap-1 bg-black/70 backdrop-blur-sm rounded-lg p-1 shadow-lg">
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

                <div className={cn(playerTab === "player" ? "" : "hidden")}>
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
                                    {generatingVideo ? "Regenerating Video..." : "Generate Lecture Video"}
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
                            voiceoverId={selectedVoiceoverId}
                            subtitles={playerSubtitles}
                            subtitleMode={playerSubtitleMode}
                            onSubtitleModeChange={(mode) => setPlayerSubtitleMode(mode as SubtitleMode)}
                            onTimeUpdate={onTimeUpdate}
                            onCapture={onCapture}
                            onAskAtTime={onAskAtTime}
                            onAddNoteAtTime={onAddNoteAtTime}
                            onPlayerReady={onPlayerReady}
                        />
                    )}
                </div>
                <div
                    ref={slideContainerRef}
                    className={cn(
                        "relative w-full bg-card rounded-xl border border-border shadow-sm overflow-hidden group flex items-center justify-center bg-black",
                        isSlideFullscreen ? "h-full" : "aspect-video",
                        playerTab === "slide" ? "" : "hidden"
                    )}
                >
                    {renderSlideTab()}

                    {/* Fullscreen button - only show when slide tab is active and has content */}
                    {playerTab === "slide" && (content.type === "slide" || (slideDeck && slideDeck.id)) && (
                        <div className="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity z-20">
                            <button
                                onClick={toggleSlideFullscreen}
                                className="p-2 rounded-full bg-black/50 hover:bg-black/70 text-white transition-colors"
                                title={isSlideFullscreen ? "Exit Fullscreen" : "Enter Fullscreen"}
                            >
                                {isSlideFullscreen ? (
                                    <Minimize className="w-5 h-5" />
                                ) : (
                                    <Maximize className="w-5 h-5" />
                                )}
                            </button>
                        </div>
                    )}
                </div>
            </div>
        );
    }
);

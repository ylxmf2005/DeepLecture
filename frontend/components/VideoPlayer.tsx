import { useRef, useState, forwardRef, useImperativeHandle, useEffect, useMemo } from "react";
import { Camera, Loader2, MessageSquare, FilePlus, Languages, Maximize, Minimize } from "lucide-react";
import { captureSlide, API_BASE_URL } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Subtitle } from "@/lib/srt";
import { getActiveSubtitles } from "@/lib/subtitleSearch";
import { useGlobalSettingsStore } from "@/stores";

interface VideoPlayerProps {
    videoId: string;
    voiceoverId?: string | null;
    subtitles?: Subtitle[];
    subtitleMode?: string;
    onSubtitleModeChange?: (mode: string) => void;
    onTimeUpdate?: (currentTime: number) => void;
    onCapture?: (timestamp: number, imagePath: string) => void;
    onAskAtTime?: (time: number) => void;
    onAddNoteAtTime?: (time: number) => void;
    onPlayerReady?: (videoElement: HTMLVideoElement) => void;
}

export interface VideoPlayerRef {
    getCurrentTime: () => number;
    seekTo: (time: number) => void;
    play: () => void;
    pause: () => void;
    isPlaying: () => boolean;
    getVideoElement: () => HTMLVideoElement | null;
}

export const VideoPlayer = forwardRef<VideoPlayerRef, VideoPlayerProps>(
    ({
        videoId,
        voiceoverId,
        subtitles,
        subtitleMode,
        onSubtitleModeChange,
        onTimeUpdate,
        onCapture,
        onAskAtTime,
        onAddNoteAtTime,
        onPlayerReady,
    }, ref) => {
        const videoRef = useRef<HTMLVideoElement>(null);
        const [isCapturing, setIsCapturing] = useState(false);
        const [currentTime, setCurrentTime] = useState(0);
        const [showLanguageMenu, setShowLanguageMenu] = useState(false);

        useImperativeHandle(ref, () => ({
            getCurrentTime: () => videoRef.current?.currentTime || 0,
            seekTo: (time: number) => {
                if (videoRef.current) {
                    videoRef.current.currentTime = time;
                }
            },
            play: () => videoRef.current?.play(),
            pause: () => videoRef.current?.pause(),
            isPlaying: () => !!(videoRef.current && !videoRef.current.paused && !videoRef.current.ended),
            getVideoElement: () => videoRef.current,
        }));

        useEffect(() => {
            if (!onPlayerReady) return;
            const videoElement = videoRef.current;
            if (!videoElement) return;

            let cancelled = false;

            const handleReady = () => {
                if (cancelled || !videoRef.current) return;
                onPlayerReady(videoRef.current);
            };

            if (videoElement.readyState >= 1) {
                handleReady();
            } else {
                videoElement.addEventListener("loadedmetadata", handleReady);
            }

            return () => {
                cancelled = true;
                videoElement.removeEventListener("loadedmetadata", handleReady);
            };
        }, [onPlayerReady, voiceoverId]);


        const handleTimeUpdate = () => {
            if (videoRef.current) {
                const time = videoRef.current.currentTime;
                setCurrentTime(time);
                if (onTimeUpdate) {
                    onTimeUpdate(time);
                }
            }
        };

        const handleAsk = () => {
            if (!videoRef.current || !onAskAtTime) return;
            onAskAtTime(videoRef.current.currentTime);
        };

        const handleAddNote = () => {
            if (!videoRef.current || !onAddNoteAtTime) return;
            onAddNoteAtTime(videoRef.current.currentTime);
        };

        const handleCapture = async () => {
            if (!videoRef.current) return;

            try {
                setIsCapturing(true);
                const timestamp = videoRef.current.currentTime;
                const data = await captureSlide(videoId, timestamp);

                if (onCapture) {
                    onCapture(timestamp, data.image_path);
                }
            } catch (error) {
                console.error("Failed to capture slide:", error);
            } finally {
                setIsCapturing(false);
            }
        };

        const toggleLanguageMenu = () => {
            setShowLanguageMenu(!showLanguageMenu);
        };

        const handleLanguageSelect = (mode: string) => {
            if (onSubtitleModeChange) {
                onSubtitleModeChange(mode);
            }
            setShowLanguageMenu(false);
        };

        // Filter active subtitles for the overlay using binary search
        // O(log n) instead of O(n) - 100x faster for 1000 subtitles
        const activeSubtitles = useMemo(() => {
            return getActiveSubtitles(subtitles || [], currentTime);
        }, [subtitles, currentTime]);

        const containerRef = useRef<HTMLDivElement>(null);
        const [isFullscreen, setIsFullscreen] = useState(false);

        // Global subtitle display preferences (per-user)
        const subtitleDisplay = useGlobalSettingsStore((s) => s.subtitleDisplay);

        useEffect(() => {
            const handleFullscreenChange = () => {
                setIsFullscreen(!!document.fullscreenElement);
            };

            document.addEventListener("fullscreenchange", handleFullscreenChange);
            return () => {
                document.removeEventListener("fullscreenchange", handleFullscreenChange);
            };
        }, []);

        const toggleFullscreen = async () => {
            if (!containerRef.current) return;

            try {
                if (!document.fullscreenElement) {
                    await containerRef.current.requestFullscreen();
                } else {
                    await document.exitFullscreen();
                }
            } catch (err) {
                console.error("Error toggling fullscreen:", err);
            }
        };

        // ... existing useEffects ...

        return (
            <div
                ref={containerRef}
                className="relative group rounded-xl overflow-hidden bg-black shadow-lg flex items-center justify-center bg-black"
            >
                <video
                    key={voiceoverId ?? "original"}
                    ref={videoRef}
                    className={cn(
                        "w-full",
                        isFullscreen ? "h-full object-contain" : "aspect-video"
                    )}
                    controls
                    crossOrigin="anonymous"
                    onTimeUpdate={handleTimeUpdate}
                    controlsList="nodownload noremoteplayback"
                >
                    <source
                        src={
                            voiceoverId
                                ? `${API_BASE_URL}/api/content/${videoId}/voiceovers/${encodeURIComponent(
                                      voiceoverId
                                  )}/video`
                                : `${API_BASE_URL}/api/content/${videoId}/video`
                        }
                        type="video/mp4"
                    />
                    {/* Intentionally NOT rendering <track> elements to avoid native subtitles */}
                    Your browser does not support the video tag.
                </video>

                {/* Custom Subtitle Overlay - positioned above progress bar with lower z-index */}
                {subtitleMode !== "off" && subtitles && subtitles.length > 0 && activeSubtitles.length > 0 && (
                    <div
                        className="absolute left-0 right-0 flex flex-col items-center justify-end px-8 pointer-events-none z-[1]"
                        style={{
                            bottom: subtitleDisplay?.bottomOffset ?? 56,
                        }}
                    >
                        {activeSubtitles.map((sub, index) => (
                            <div
                                key={`${sub.startTime}-${index}`}
                                className="bg-black/70 text-white text-center px-4 py-1 rounded-lg mb-1 max-w-[80%] whitespace-pre-wrap"
                                style={{
                                    fontSize: `${
                                        (subtitleDisplay?.fontSize ?? 16) * (isFullscreen ? 2 : 1)
                                    }px`,
                                    lineHeight: "1.5",
                                    textShadow: "0px 1px 2px rgba(0,0,0,0.8)"
                                }}
                            >
                                {sub.text}
                            </div>
                        ))}
                    </div>
                )}

                <div className="absolute top-4 right-4 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity z-20">
                    {onSubtitleModeChange && (
                        <div className="relative">
                            <button
                                onClick={toggleLanguageMenu}
                                className="p-2 rounded-full bg-black/50 hover:bg-black/70 text-white transition-colors"
                                title="Subtitle Language"
                            >
                                <Languages className="w-5 h-5" />
                            </button>
                            {showLanguageMenu && (
                                <div className="absolute top-full right-0 mt-2 bg-black/90 border border-gray-700 rounded-lg shadow-xl overflow-hidden min-w-[120px] flex flex-col">
                                    <button
                                        onClick={() => handleLanguageSelect("off")}
                                        className={cn(
                                            "px-4 py-2 text-sm text-left hover:bg-white/10 transition-colors",
                                            subtitleMode === "off" ? "text-blue-400 font-medium" : "text-white"
                                        )}
                                    >
                                        Off
                                    </button>
                                    <button
                                        onClick={() => handleLanguageSelect("en")}
                                        className={cn(
                                            "px-4 py-2 text-sm text-left hover:bg-white/10 transition-colors",
                                            subtitleMode === "en" ? "text-blue-400 font-medium" : "text-white"
                                        )}
                                    >
                                        English
                                    </button>
                                    <button
                                        onClick={() => handleLanguageSelect("zh")}
                                        className={cn(
                                            "px-4 py-2 text-sm text-left hover:bg-white/10 transition-colors",
                                            subtitleMode === "zh" ? "text-blue-400 font-medium" : "text-white"
                                        )}
                                    >
                                        Chinese
                                    </button>
                                    <button
                                        onClick={() => handleLanguageSelect("en_zh")}
                                        className={cn(
                                            "px-4 py-2 text-sm text-left hover:bg-white/10 transition-colors",
                                            subtitleMode === "en_zh" ? "text-blue-400 font-medium" : "text-white"
                                        )}
                                    >
                                        Bilingual (EN+ZH)
                                    </button>
                                    <button
                                        onClick={() => handleLanguageSelect("zh_en")}
                                        className={cn(
                                            "px-4 py-2 text-sm text-left hover:bg-white/10 transition-colors",
                                            subtitleMode === "zh_en" ? "text-blue-400 font-medium" : "text-white"
                                        )}
                                    >
                                        Bilingual (ZH+EN)
                                    </button>
                                </div>
                            )}
                        </div>
                    )}

                    {onAskAtTime && (
                        <button
                            onClick={handleAsk}
                            className="p-2 rounded-full bg-black/50 hover:bg-black/70 text-white transition-colors"
                            title="Ask AI about this moment"
                        >
                            <MessageSquare className="w-5 h-5" />
                        </button>
                    )}

                    {onAddNoteAtTime && (
                        <button
                            onClick={handleAddNote}
                            className="p-2 rounded-full bg-black/50 hover:bg-black/70 text-white transition-colors"
                            title="Add this moment to notes"
                        >
                            <FilePlus className="w-5 h-5" />
                        </button>
                    )}

                    <button
                        onClick={handleCapture}
                        disabled={isCapturing}
                        className={cn(
                            "p-2 rounded-full bg-black/50 hover:bg-black/70 text-white transition-colors",
                            isCapturing && "cursor-not-allowed opacity-75"
                        )}
                        title="Capture Slide & Explain"
                    >
                        {isCapturing ? (
                            <Loader2 className="w-5 h-5 animate-spin" />
                        ) : (
                            <Camera className="w-5 h-5" />
                        )}
                    </button>

                    <button
                        onClick={toggleFullscreen}
                        className="p-2 rounded-full bg-black/50 hover:bg-black/70 text-white transition-colors"
                        title={isFullscreen ? "Exit Fullscreen" : "Enter Fullscreen"}
                    >
                        {isFullscreen ? (
                            <Minimize className="w-5 h-5" />
                        ) : (
                            <Maximize className="w-5 h-5" />
                        )}
                    </button>
                </div>
            </div>
        );
    }
);

VideoPlayer.displayName = "VideoPlayer";

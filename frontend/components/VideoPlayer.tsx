import { useRef, useState, forwardRef, useImperativeHandle, useEffect, useMemo, useCallback } from "react";
import { Camera, Loader2, MessageSquare, FilePlus, Languages } from "lucide-react";
import { captureSlide, API_BASE_URL, SyncTimeline } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Subtitle } from "@/lib/srt";
import { getActiveSubtitles } from "@/lib/subtitleSearch";
import { useGlobalSettingsStore } from "@/stores";
import { useVoiceoverSync } from "@/hooks/useVoiceoverSync";
import { VideoControls } from "./VideoControls";

interface VideoPlayerProps {
    videoId: string;
    voiceoverId?: string | null;
    /** Sync timeline for playback-side A/V sync (when voiceoverId is set) */
    syncTimeline?: SyncTimeline | null;
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
        syncTimeline,
        subtitles,
        subtitleMode,
        onSubtitleModeChange,
        onTimeUpdate,
        onCapture,
        onAskAtTime,
        onAddNoteAtTime,
        onPlayerReady,
    }, ref) => {
        const [isCapturing, setIsCapturing] = useState(false);
        const [currentTime, setCurrentTime] = useState(0);
        const [duration, setDuration] = useState(0);
        const [isPlaying, setIsPlaying] = useState(false);
        const [showLanguageMenu, setShowLanguageMenu] = useState(false);
        const containerRef = useRef<HTMLDivElement>(null);
        const [isFullscreen, setIsFullscreen] = useState(false);

        // Voiceover sync hook
        const {
            videoRef,
            audioRef,
            isActive: isSyncActive,
            startSync,
            stopSync,
            seekToVideoTime,
            setUserRate,
            play: syncPlay,
            pause: syncPause,
            getCurrentVideoTime,
        } = useVoiceoverSync();

        // Expose ref methods
        useImperativeHandle(ref, () => ({
            getCurrentTime: () => {
                // Always return video time for external consumers
                return getCurrentVideoTime();
            },
            seekTo: (time: number) => {
                // External callers always pass video time
                // seekToVideoTime handles conversion to audio time internally when in sync mode
                seekToVideoTime(time);
            },
            play: () => {
                if (isSyncActive) {
                    syncPlay();
                } else {
                    videoRef.current?.play();
                }
            },
            pause: () => {
                if (isSyncActive) {
                    syncPause();
                } else {
                    videoRef.current?.pause();
                }
            },
            isPlaying: () => !!(videoRef.current && !videoRef.current.paused && !videoRef.current.ended),
            getVideoElement: () => videoRef.current,
        }));

        // Handle voiceover mode changes
        useEffect(() => {
            if (voiceoverId && syncTimeline) {
                // Start sync mode
                startSync(syncTimeline);
            } else {
                // Stop sync mode (if was active)
                stopSync();
            }
        }, [voiceoverId, syncTimeline, startSync, stopSync]);

        // Notify parent when player is ready
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
        }, [onPlayerReady, videoId]);

        const handleTimeUpdate = useCallback(() => {
            // CRITICAL: Always output VIDEO time to external consumers
            // Subtitles, timeline markers, progress persistence all use video time
            // The sync hook handles audio/video coordination internally
            const time = videoRef.current?.currentTime ?? 0;

            setCurrentTime(time);
            onTimeUpdate?.(time);
        }, [onTimeUpdate, videoRef]);

        // Set up video event listeners
        useEffect(() => {
            const video = videoRef.current;
            if (!video) return;

            const handleDurationChange = () => setDuration(video.duration || 0);
            const handlePlay = () => setIsPlaying(true);
            const handlePause = () => setIsPlaying(false);
            const handleEnded = () => setIsPlaying(false);

            video.addEventListener("timeupdate", handleTimeUpdate);
            video.addEventListener("durationchange", handleDurationChange);
            video.addEventListener("loadedmetadata", handleDurationChange);
            video.addEventListener("play", handlePlay);
            video.addEventListener("pause", handlePause);
            video.addEventListener("ended", handleEnded);

            // Initialize duration if already loaded
            if (video.duration) {
                setDuration(video.duration);
            }

            return () => {
                video.removeEventListener("timeupdate", handleTimeUpdate);
                video.removeEventListener("durationchange", handleDurationChange);
                video.removeEventListener("loadedmetadata", handleDurationChange);
                video.removeEventListener("play", handlePlay);
                video.removeEventListener("pause", handlePause);
                video.removeEventListener("ended", handleEnded);
            };
        }, [handleTimeUpdate, videoRef]);

        // Custom control handlers
        const handlePlay = useCallback(() => {
            if (isSyncActive) {
                syncPlay();
            } else {
                videoRef.current?.play();
            }
        }, [isSyncActive, syncPlay, videoRef]);

        const handlePause = useCallback(() => {
            if (isSyncActive) {
                syncPause();
            } else {
                videoRef.current?.pause();
            }
        }, [isSyncActive, syncPause, videoRef]);

        const handleSeek = useCallback((time: number) => {
            seekToVideoTime(time);
        }, [seekToVideoTime]);

        const handleAsk = () => {
            if (!onAskAtTime) return;
            onAskAtTime(currentTime);
        };

        const handleAddNote = () => {
            if (!onAddNoteAtTime) return;
            onAddNoteAtTime(currentTime);
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
        const activeSubtitles = useMemo(() => {
            return getActiveSubtitles(subtitles || [], currentTime);
        }, [subtitles, currentTime]);

        // Global subtitle display preferences
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

        // Build audio URL for voiceover
        const voiceoverAudioUrl = voiceoverId
            ? `${API_BASE_URL}/api/content/${videoId}/voiceovers/${encodeURIComponent(voiceoverId)}/audio`
            : null;

        return (
            <div
                ref={containerRef}
                className="relative group rounded-xl overflow-hidden bg-black shadow-lg flex items-center justify-center bg-black"
            >
                {/* Video element without native controls */}
                <video
                    ref={videoRef}
                    className={cn(
                        "w-full",
                        isFullscreen ? "h-full object-contain" : "aspect-video"
                    )}
                    crossOrigin="anonymous"
                    onClick={isPlaying ? handlePause : handlePlay}
                >
                    <source
                        src={`${API_BASE_URL}/api/content/${videoId}/video`}
                        type="video/mp4"
                    />
                    Your browser does not support the video tag.
                </video>

                {/* Hidden audio element for voiceover sync */}
                {voiceoverAudioUrl && (
                    <audio
                        ref={audioRef}
                        src={voiceoverAudioUrl}
                        preload="auto"
                        style={{ display: "none" }}
                    />
                )}

                {/* Custom Subtitle Overlay */}
                {subtitleMode !== "off" && subtitles && subtitles.length > 0 && activeSubtitles.length > 0 && (
                    <div
                        className="absolute left-0 right-0 flex flex-col items-center justify-end px-8 pointer-events-none z-[1]"
                        style={{
                            bottom: (subtitleDisplay?.bottomOffset ?? 56) + 48, // Add space for custom controls
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

                {/* Custom Video Controls */}
                <VideoControls
                    videoRef={videoRef}
                    audioRef={audioRef}
                    isSyncActive={isSyncActive}
                    onSetUserRate={setUserRate}
                    currentTime={currentTime}
                    duration={duration}
                    isPlaying={isPlaying}
                    onPlay={handlePlay}
                    onPause={handlePause}
                    onSeek={handleSeek}
                    isFullscreen={isFullscreen}
                    onToggleFullscreen={toggleFullscreen}
                />

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
                </div>
            </div>
        );
    }
);

VideoPlayer.displayName = "VideoPlayer";

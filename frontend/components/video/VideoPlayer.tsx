import { useRef, useState, forwardRef, useImperativeHandle, useEffect, useMemo, useCallback } from "react";
import { Camera, Loader2, MessageSquare, FilePlus, Languages } from "lucide-react";
import { captureSlide, API_BASE_URL, SyncTimeline } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Subtitle } from "@/lib/srt";
import { getActiveSubtitles } from "@/lib/subtitleSearch";
import { useGlobalSettingsStore } from "@/stores";
import type { SubtitleDisplayMode, ViewMode } from "@/stores/types";
import { useVoiceoverSync } from "@/hooks/useVoiceoverSync";
import { VideoControls } from "./VideoControls";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";

const log = logger.scope("VideoPlayer");

/** Player subtitle mode: semantic display mode + "off" for hiding subtitles */
export type SubtitlePlayerMode = SubtitleDisplayMode | "off";

interface VideoPlayerProps {
    videoId: string;
    title?: string; // Video title for Media Session
    voiceoverId?: string | null;
    /** Sync timeline for playback-side A/V sync (when voiceoverId is set) */
    syncTimeline?: SyncTimeline | null;
    subtitles?: Subtitle[];
    subtitleMode?: SubtitlePlayerMode;
    onSubtitleModeChange?: (mode: SubtitlePlayerMode) => void;
    onTimeUpdate?: (currentTime: number) => void;
    onCapture?: (timestamp: number, imagePath: string) => void;
    onAskAtTime?: (time: number) => void;
    onAddNoteAtTime?: (time: number) => void;
    onPlayerReady?: (videoElement: HTMLVideoElement) => void;
    /** Current view mode for layout control */
    viewMode?: ViewMode;
    /** Callback when view mode changes */
    onViewModeChange?: (mode: ViewMode) => void;
}

export interface VideoPlayerRef {
    getCurrentTime: () => number;
    seekTo: (time: number) => void;
    play: () => void;
    pause: () => void;
    isPlaying: () => boolean;
    getVideoElement: () => HTMLVideoElement | null;
    getAudioElement: () => HTMLAudioElement | null;
    isSyncActive: () => boolean;
}

export const VideoPlayer = forwardRef<VideoPlayerRef, VideoPlayerProps>(
    ({
        videoId,
        title,
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
        viewMode,
        onViewModeChange,
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
                // Always delegate to syncPlay - it uses isActiveRef internally,
                // avoiding race conditions with the lagging isSyncActive state
                syncPlay();
            },
            pause: () => {
                // Always delegate to syncPause for consistent behavior
                syncPause();
            },
            isPlaying: () => !!(videoRef.current && !videoRef.current.paused && !videoRef.current.ended),
            getVideoElement: () => videoRef.current,
            getAudioElement: () => audioRef.current,
            isSyncActive: () => isSyncActive,
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

        // Custom control handlers defined early for Media Session
        // Always delegate to sync hooks - they use isActiveRef internally to decide
        // whether to control audio+video (sync mode) or just video (normal mode),
        // avoiding race conditions with the lagging isSyncActive state
        const handlePlay = useCallback(() => {
            syncPlay();
        }, [syncPlay]);

        const handlePause = useCallback(() => {
            syncPause();
        }, [syncPause]);

        const handleSeek = useCallback((time: number) => {
            seekToVideoTime(time);
        }, [seekToVideoTime]);

        // Keyboard shortcuts
        const handleKeyDown = useCallback((e: KeyboardEvent) => {
            // Skip if user is typing in an input field
            const target = e.target as HTMLElement;
            if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) {
                return;
            }

            const video = videoRef.current;
            if (!video) return;

            switch (e.key) {
                case " ":
                case "Spacebar":
                    e.preventDefault();
                    if (video.paused) {
                        handlePlay();
                    } else {
                        handlePause();
                    }
                    break;
                case "ArrowLeft":
                    e.preventDefault();
                    handleSeek(Math.max(0, getCurrentVideoTime() - 5));
                    break;
                case "ArrowRight":
                    e.preventDefault();
                    handleSeek(Math.min(duration, getCurrentVideoTime() + 5));
                    break;
                case "ArrowUp":
                    e.preventDefault();
                    if (video) {
                        video.volume = Math.min(1, video.volume + 0.1);
                    }
                    break;
                case "ArrowDown":
                    e.preventDefault();
                    if (video) {
                        video.volume = Math.max(0, video.volume - 0.1);
                    }
                    break;
            }
        }, [handlePlay, handlePause, handleSeek, getCurrentVideoTime, duration, videoRef]);

        // Global keyboard listener
        useEffect(() => {
            document.addEventListener("keydown", handleKeyDown);
            return () => {
                document.removeEventListener("keydown", handleKeyDown);
            };
        }, [handleKeyDown]);

        // Media Session API integration
        useEffect(() => {
            if (!("mediaSession" in navigator)) return;

            // Set metadata
            navigator.mediaSession.metadata = new MediaMetadata({
                title: title || "Course Video",
                // artwork: [] // Could add thumbnails here if available
            });

            // Set action handlers
            const actionHandlers = [
                ["play", handlePlay],
                ["pause", handlePause],
                ["seekbackward", () => handleSeek(Math.max(0, getCurrentVideoTime() - 10))],
                ["seekforward", () => handleSeek(getCurrentVideoTime() + 10)],
                ["seekto", (details: MediaSessionActionDetails) => {
                    if (details.seekTime !== undefined && details.seekTime !== null) {
                        handleSeek(details.seekTime);
                    }
                }],
            ] as const;

            for (const [action, handler] of actionHandlers) {
                try {
                    navigator.mediaSession.setActionHandler(action as MediaSessionAction, handler);
                } catch (error) {
                    log.warn(`Media Session action ${action} not supported`);
                }
            }

            return () => {
                // Clean up handlers (though usually overwriting them is fine)
                for (const [action] of actionHandlers) {
                    try {
                        navigator.mediaSession.setActionHandler(action as MediaSessionAction, null);
                    } catch {
                        // ignore
                    }
                }
            };
        }, [title, handlePlay, handlePause, handleSeek, getCurrentVideoTime]);

        // Update Media Session playback state
        useEffect(() => {
            if ("mediaSession" in navigator) {
                navigator.mediaSession.playbackState = isPlaying ? "playing" : "paused";
            }
        }, [isPlaying]);

        // Update Media Session position state (helps browser understand active playback)
        useEffect(() => {
            if (!("mediaSession" in navigator) || !duration || duration <= 0) return;

            try {
                navigator.mediaSession.setPositionState({
                    duration: duration,
                    playbackRate: videoRef.current?.playbackRate || 1,
                    position: Math.min(currentTime, duration),
                });
            } catch {
                // setPositionState may throw if values are invalid
            }
        }, [currentTime, duration, videoRef]);

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
        }, [onPlayerReady, videoId, videoRef]);

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
        // Note: handlePlay, handlePause, handleSeek are defined earlier for Media Session

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
                    onCapture(timestamp, data.imagePath ?? data.imageUrl);
                }
            } catch (error) {
                log.error("Failed to capture slide", toError(error), { videoId });
            } finally {
                setIsCapturing(false);
            }
        };

        const toggleLanguageMenu = () => {
            setShowLanguageMenu(!showLanguageMenu);
        };

        const handleLanguageSelect = (mode: SubtitlePlayerMode) => {
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
                log.error("Failed to toggle fullscreen", toError(err));
            }
        };

        // Build audio URL for voiceover
        const voiceoverAudioUrl = voiceoverId
            ? `${API_BASE_URL}/api/content/${videoId}/voiceovers/${encodeURIComponent(voiceoverId)}/audio`
            : null;

        return (
            <div
                ref={containerRef}
                className="relative group rounded-xl bg-black shadow-lg flex items-center justify-center"
            >
                {/* Video element without native controls */}
                <video
                    ref={videoRef}
                    className={cn(
                        "w-full rounded-xl",
                        isFullscreen ? "h-full object-contain" : "aspect-video"
                    )}
                    crossOrigin="anonymous"
                    playsInline
                    onClick={isPlaying ? handlePause : handlePlay}
                >
                    <source
                        src={`${API_BASE_URL}/api/content/${videoId}/video`}
                    />
                    Your browser does not support the video tag.
                </video>

                {/* Hidden audio element for voiceover sync */}
                {voiceoverAudioUrl && (
                    <audio
                        ref={audioRef}
                        src={voiceoverAudioUrl}
                        crossOrigin="anonymous"
                        preload="auto"
                        style={{ display: "none" }}
                    />
                )}

                {/* Custom Subtitle Overlay */}
                {subtitleMode !== "off" && subtitles && subtitles.length > 0 && activeSubtitles.length > 0 && (
                    <div
                        className="absolute left-0 right-0 flex flex-col items-center justify-end px-8 pointer-events-none z-[1]"
                        style={{
                            bottom: subtitleDisplay?.bottomOffset ?? 72,
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
                    viewMode={viewMode}
                    onViewModeChange={onViewModeChange}
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
                                        onClick={() => handleLanguageSelect("source")}
                                        className={cn(
                                            "px-4 py-2 text-sm text-left hover:bg-white/10 transition-colors",
                                            subtitleMode === "source" ? "text-blue-400 font-medium" : "text-white"
                                        )}
                                    >
                                        Source
                                    </button>
                                    <button
                                        onClick={() => handleLanguageSelect("target")}
                                        className={cn(
                                            "px-4 py-2 text-sm text-left hover:bg-white/10 transition-colors",
                                            subtitleMode === "target" ? "text-blue-400 font-medium" : "text-white"
                                        )}
                                    >
                                        Target
                                    </button>
                                    <button
                                        onClick={() => handleLanguageSelect("dual")}
                                        className={cn(
                                            "px-4 py-2 text-sm text-left hover:bg-white/10 transition-colors",
                                            subtitleMode === "dual" ? "text-blue-400 font-medium" : "text-white"
                                        )}
                                    >
                                        Dual
                                    </button>
                                    <button
                                        onClick={() => handleLanguageSelect("dual_reversed")}
                                        className={cn(
                                            "px-4 py-2 text-sm text-left hover:bg-white/10 transition-colors",
                                            subtitleMode === "dual_reversed" ? "text-blue-400 font-medium" : "text-white"
                                        )}
                                    >
                                        Dual (Reversed)
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

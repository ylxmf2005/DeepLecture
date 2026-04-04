"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
    Play,
    Pause,
    Volume2,
    VolumeX,
    Volume1,
    Maximize,
    Minimize,
    Maximize2,
    Minimize2,
    ChevronsLeftRight,
    ChevronsRightLeft,
} from "lucide-react";
import type { ViewMode } from "@/stores/types";
import { cn } from "@/lib/utils";
import { VideoProgressBar } from "./VideoProgressBar";

interface VideoControlsProps {
    /** Video element to control */
    videoRef: React.RefObject<HTMLVideoElement | null>;
    /** Audio element to control (for voiceover mode) */
    audioRef?: React.RefObject<HTMLAudioElement | null>;
    /** Whether voiceover sync is active */
    isSyncActive?: boolean;
    /** Callback to set user playback rate (for voiceover sync) */
    onSetUserRate?: (rate: number) => void;
    /** Current time in seconds */
    currentTime: number;
    /** Duration in seconds */
    duration: number;
    /** Whether video is playing */
    isPlaying: boolean;
    /** Play callback */
    onPlay: () => void;
    /** Pause callback */
    onPause: () => void;
    /** Seek callback (video time) */
    onSeek: (time: number) => void;
    /** Whether fullscreen is active */
    isFullscreen: boolean;
    /** Toggle fullscreen callback */
    onToggleFullscreen: () => void;
    /** Current view mode */
    viewMode?: ViewMode;
    /** View mode change callback */
    onViewModeChange?: (mode: ViewMode) => void;
    /** Bookmark timestamps to display as dots on the progress bar */
    bookmarkTimestamps?: number[];
    /** Optional className */
    className?: string;
}

const PLAYBACK_RATES = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2];

function formatTime(seconds: number): string {
    if (!isFinite(seconds) || isNaN(seconds)) return "0:00";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) {
        return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
    }
    return `${m}:${s.toString().padStart(2, "0")}`;
}

export function VideoControls({
    videoRef,
    audioRef,
    isSyncActive = false,
    onSetUserRate,
    currentTime,
    duration,
    isPlaying,
    onPlay,
    onPause,
    onSeek,
    isFullscreen,
    onToggleFullscreen,
    viewMode = "normal",
    onViewModeChange,
    bookmarkTimestamps,
    className,
}: VideoControlsProps) {
    const [volume, setVolume] = useState(1);
    const [isMuted, setIsMuted] = useState(false);
    const [previousVolume, setPreviousVolume] = useState(1);
    const [playbackRate, setPlaybackRate] = useState(1);
    const [showSpeedMenu, setShowSpeedMenu] = useState(false);
    const [isDraggingVolume, setIsDraggingVolume] = useState(false);
    const [isInitialized, setIsInitialized] = useState(false);

    const volumeSliderRef = useRef<HTMLDivElement>(null);
    const speedMenuRef = useRef<HTMLDivElement>(null);
    const prevSyncActiveRef = useRef(isSyncActive);

    // Initialize and sync volume/muted state from media element
    // This syncs React state with external media element state (valid use case)
    useEffect(() => {
        const target = isSyncActive ? audioRef?.current : videoRef.current;

        // Only sync on source change (video <-> audio) or initial mount
        if (!isInitialized || prevSyncActiveRef.current !== isSyncActive) {
            prevSyncActiveRef.current = isSyncActive;
            if (target) {
                // eslint-disable-next-line react-hooks/set-state-in-effect -- Syncing React state with external media element
                setVolume(target.volume);

                setIsMuted(target.muted);
            }
            if (!isInitialized) {

                setIsInitialized(true);
            }
        }
    }, [isSyncActive, audioRef, videoRef, isInitialized]);

    // Initialize playback rate from video element
    useEffect(() => {
        const video = videoRef.current;
        if (video && !isSyncActive && !isInitialized) {

            setPlaybackRate(video.playbackRate);
        }
    }, [videoRef, isSyncActive, isInitialized]);

    // Apply volume changes
    const applyVolume = useCallback((newVolume: number, muted: boolean) => {
        if (isSyncActive && audioRef?.current) {
            // In sync mode, control audio element
            audioRef.current.volume = newVolume;
            audioRef.current.muted = muted;
            // Video stays muted
            if (videoRef.current) {
                videoRef.current.muted = true;
            }
        } else if (videoRef.current) {
            // Normal mode, control video element
            videoRef.current.volume = newVolume;
            videoRef.current.muted = muted;
        }
    }, [isSyncActive, audioRef, videoRef]);

    // Handle volume change
    const handleVolumeChange = useCallback((newVolume: number) => {
        setVolume(newVolume);
        setIsMuted(newVolume === 0);
        applyVolume(newVolume, newVolume === 0);
    }, [applyVolume]);

    // Handle mute toggle
    const handleMuteToggle = useCallback(() => {
        if (isMuted) {
            // Unmute - restore previous volume
            const restoreVolume = previousVolume > 0 ? previousVolume : 1;
            setVolume(restoreVolume);
            setIsMuted(false);
            applyVolume(restoreVolume, false);
        } else {
            // Mute - save current volume
            setPreviousVolume(volume);
            setIsMuted(true);
            applyVolume(volume, true);
        }
    }, [isMuted, volume, previousVolume, applyVolume]);

    // Handle playback rate change
    const handlePlaybackRateChange = useCallback((rate: number) => {
        setPlaybackRate(rate);
        setShowSpeedMenu(false);

        if (isSyncActive && onSetUserRate) {
            // In sync mode, use the sync hook's rate setter
            onSetUserRate(rate);
        } else if (videoRef.current) {
            // Normal mode, set video playback rate directly
            videoRef.current.playbackRate = rate;
        }
    }, [isSyncActive, onSetUserRate, videoRef]);

    // Volume slider drag handling
    const handleVolumeMouseDown = useCallback((e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDraggingVolume(true);
    }, []);

    const handleVolumeClick = useCallback((e: React.MouseEvent) => {
        if (!volumeSliderRef.current) return;
        const rect = volumeSliderRef.current.getBoundingClientRect();
        const percent = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        handleVolumeChange(percent);
    }, [handleVolumeChange]);

    // Global mouse move/up handlers for volume dragging
    useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {
            if (isDraggingVolume && volumeSliderRef.current) {
                const rect = volumeSliderRef.current.getBoundingClientRect();
                const percent = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
                handleVolumeChange(percent);
            }
        };

        const handleMouseUp = () => {
            setIsDraggingVolume(false);
        };

        if (isDraggingVolume) {
            document.addEventListener("mousemove", handleMouseMove);
            document.addEventListener("mouseup", handleMouseUp);
        }

        return () => {
            document.removeEventListener("mousemove", handleMouseMove);
            document.removeEventListener("mouseup", handleMouseUp);
        };
    }, [isDraggingVolume, handleVolumeChange]);

    // Close menus when clicking outside
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (speedMenuRef.current && !speedMenuRef.current.contains(e.target as Node)) {
                setShowSpeedMenu(false);
            }
        };

        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const VolumeIcon = isMuted || volume === 0 ? VolumeX : volume < 0.5 ? Volume1 : Volume2;

    return (
        <div
            className={cn(
                "absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent px-4 py-3 opacity-0 group-hover:opacity-100 transition-opacity z-10",
                className
            )}
            onClick={(e) => e.stopPropagation()}
        >
            {/* Progress bar */}
            <VideoProgressBar
                currentTime={currentTime}
                duration={duration}
                onSeek={onSeek}
                bookmarkTimestamps={bookmarkTimestamps}
                className="mb-3"
            />

            {/* Controls row */}
            <div className="flex items-center justify-between">
                {/* Left controls */}
                <div className="flex items-center gap-3">
                    {/* Play/Pause */}
                    <button
                        onClick={isPlaying ? onPause : onPlay}
                        className="p-1 text-white hover:text-white/80 transition-colors"
                        title={isPlaying ? "Pause" : "Play"}
                    >
                        {isPlaying ? (
                            <Pause className="w-5 h-5" fill="currentColor" />
                        ) : (
                            <Play className="w-5 h-5" fill="currentColor" />
                        )}
                    </button>

                    {/* Volume */}
                    <div className="flex items-center gap-2">
                        <button
                            onClick={handleMuteToggle}
                            className="p-1 text-white hover:text-white/80 transition-colors"
                            title={isMuted ? "Unmute" : "Mute"}
                        >
                            <VolumeIcon className="w-5 h-5" />
                        </button>

                        <div
                            className={cn(
                                "flex items-center w-24 sm:w-28 py-2",
                                isDraggingVolume && "cursor-grabbing"
                            )}
                        >
                            <div
                                ref={volumeSliderRef}
                                className={cn(
                                    "w-full h-1.5 bg-white/30 rounded-full cursor-pointer transition-colors",
                                    isDraggingVolume ? "bg-white/40" : "hover:bg-white/40"
                                )}
                                onClick={handleVolumeClick}
                                onMouseDown={handleVolumeMouseDown}
                            >
                                <div
                                    className="h-full bg-white rounded-full"
                                    style={{ width: `${(isMuted ? 0 : volume) * 100}%` }}
                                />
                            </div>
                        </div>
                    </div>

                    {/* Time display */}
                    <span className="text-white text-sm tabular-nums">
                        {formatTime(currentTime)} / {formatTime(duration)}
                    </span>
                </div>

                {/* Right controls */}
                <div className="flex items-center gap-3">
                    {/* Playback speed */}
                    <div ref={speedMenuRef} className="relative">
                        <button
                            onClick={() => setShowSpeedMenu(!showSpeedMenu)}
                            className="px-2 py-1 text-white text-sm hover:text-white/80 transition-colors"
                            title="Playback speed"
                        >
                            {playbackRate}x
                        </button>

                        {showSpeedMenu && (
                            <div className="absolute bottom-full right-0 mb-2 bg-black/90 border border-white/20 rounded-lg shadow-xl overflow-hidden min-w-[100px]">
                                {PLAYBACK_RATES.map((rate) => (
                                    <button
                                        key={rate}
                                        onClick={() => handlePlaybackRateChange(rate)}
                                        className={cn(
                                            "w-full px-4 py-2 text-sm text-left hover:bg-white/10 transition-colors",
                                            playbackRate === rate ? "text-blue-400 font-medium" : "text-white"
                                        )}
                                    >
                                        {rate}x
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Widescreen mode */}
                    {onViewModeChange && (
                        <button
                            onClick={() => onViewModeChange(viewMode === "widescreen" ? "normal" : "widescreen")}
                            className={cn(
                                "p-1 transition-colors",
                                viewMode === "widescreen" ? "text-blue-400" : "text-white hover:text-white/80"
                            )}
                            title={viewMode === "widescreen" ? "Exit widescreen" : "Widescreen"}
                        >
                            {viewMode === "widescreen" ? (
                                <ChevronsRightLeft className="w-5 h-5" />
                            ) : (
                                <ChevronsLeftRight className="w-5 h-5" />
                            )}
                        </button>
                    )}

                    {/* Web fullscreen mode */}
                    {onViewModeChange && (
                        <button
                            onClick={() => onViewModeChange(viewMode === "web-fullscreen" ? "normal" : "web-fullscreen")}
                            className={cn(
                                "p-1 transition-colors",
                                viewMode === "web-fullscreen" ? "text-blue-400" : "text-white hover:text-white/80"
                            )}
                            title={viewMode === "web-fullscreen" ? "Exit web fullscreen" : "Web fullscreen"}
                        >
                            {viewMode === "web-fullscreen" ? (
                                <Minimize className="w-5 h-5" />
                            ) : (
                                <Maximize className="w-5 h-5" />
                            )}
                        </button>
                    )}

                    {/* System Fullscreen */}
                    <button
                        onClick={onToggleFullscreen}
                        className={cn(
                            "p-1 transition-colors",
                            isFullscreen ? "text-blue-400" : "text-white hover:text-white/80"
                        )}
                        title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
                    >
                        {isFullscreen ? (
                            <Minimize2 className="w-5 h-5" />
                        ) : (
                            <Maximize2 className="w-5 h-5" />
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}

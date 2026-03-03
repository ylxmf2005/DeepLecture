"use client";

/**
 * PodcastTab — NotebookLM-style two-person dialogue podcast player.
 *
 * Features:
 * 1. Audio player with play/pause, seek, and progress bar.
 * 2. Scrolling transcript with speaker-colored segments.
 * 3. Click-to-seek on any transcript segment.
 * 4. Auto-scroll to current segment during playback.
 */

import { useState, useCallback, useRef, useEffect } from "react";
import {
    Mic,
    RefreshCw,
    AlertCircle,
    Loader2,
    Sparkles,
    Play,
    Pause,
    SkipBack,
    SkipForward,
} from "lucide-react";
import { getPodcast, generatePodcast, getPodcastAudioUrl } from "@/lib/api/podcast";
import type { PodcastSegment } from "@/lib/api/podcast";
import { useLanguageSettings, useNoteSettings } from "@/stores/useGlobalSettingsStore";
import { logger } from "@/shared/infrastructure";
import { useSSEGenerationRetry } from "@/hooks/useSSEGenerationRetry";
import { cn } from "@/lib/utils";

const log = logger.scope("PodcastTab");

interface PodcastTabProps {
    videoId: string;
    refreshTrigger: number;
}

interface PodcastData {
    title: string;
    summary: string;
    segments: PodcastSegment[];
    totalDuration: number;
    updatedAt: string | null;
}

function formatDuration(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
}

export function PodcastTab({ videoId, refreshTrigger }: PodcastTabProps) {
    const { translated: language } = useLanguageSettings();
    const noteSettings = useNoteSettings();

    // Audio player state
    const audioRef = useRef<HTMLAudioElement>(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [audioReady, setAudioReady] = useState(false);

    const fetchContent = useCallback(async (): Promise<PodcastData | null> => {
        const result = await getPodcast(videoId, language || "en");
        if (result && result.segments.length > 0) {
            return {
                title: result.title,
                summary: result.summary,
                segments: result.segments,
                totalDuration: result.duration,
                updatedAt: result.updatedAt,
            };
        }
        return null;
    }, [videoId, language]);

    const submitGeneration = useCallback(async () => {
        return await generatePodcast({
            contentId: videoId,
            language: language || "en",
            contextMode: noteSettings.contextMode,
            subjectType: "auto",
        });
    }, [videoId, language, noteSettings.contextMode]);

    const { data, loading, loadError, isGenerating, clearError, handleGenerate } =
        useSSEGenerationRetry<PodcastData>({
            contentId: videoId,
            refreshTrigger,
            fetchContent,
            submitGeneration,
            log,
            extraDeps: [language],
            taskType: "podcast_generation",
        });

    // Reset audio state when data changes
    useEffect(() => {
        setIsPlaying(false);
        setCurrentTime(0);
        setDuration(0);
        setAudioReady(false);
    }, [data]);

    const segments = data?.segments ?? [];
    const hasContent = segments.length > 0;
    const hasError = loadError !== null;

    // Audio URL
    const audioUrl = hasContent ? getPodcastAudioUrl(videoId, language || "en") : null;

    // Audio event handlers
    const handleTimeUpdate = useCallback(() => {
        if (audioRef.current) {
            setCurrentTime(audioRef.current.currentTime);
        }
    }, []);

    const handleLoadedMetadata = useCallback(() => {
        if (audioRef.current) {
            setDuration(audioRef.current.duration);
            setAudioReady(true);
        }
    }, []);

    const handleAudioEnded = useCallback(() => {
        setIsPlaying(false);
    }, []);

    const togglePlayPause = useCallback(() => {
        if (!audioRef.current || !audioReady) return;
        if (isPlaying) {
            audioRef.current.pause();
            setIsPlaying(false);
        } else {
            audioRef.current.play();
            setIsPlaying(true);
        }
    }, [isPlaying, audioReady]);

    const seekTo = useCallback((time: number) => {
        if (!audioRef.current) return;
        audioRef.current.currentTime = time;
        setCurrentTime(time);
    }, []);

    const skipBack = useCallback(() => {
        seekTo(Math.max(0, currentTime - 10));
    }, [currentTime, seekTo]);

    const skipForward = useCallback(() => {
        seekTo(Math.min(duration, currentTime + 10));
    }, [currentTime, duration, seekTo]);

    const handleProgressClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
        if (!duration) return;
        const rect = e.currentTarget.getBoundingClientRect();
        const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        seekTo(ratio * duration);
    }, [duration, seekTo]);

    // Find active segment
    const activeSegmentIndex = segments.findIndex(
        (seg) => currentTime >= seg.startTime && currentTime < seg.endTime
    );

    // Loading state
    if (loading && !hasContent) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-6">
                <Loader2 className="w-8 h-8 text-purple-600 animate-spin" />
                <p className="text-sm text-muted-foreground">Loading podcast...</p>
            </div>
        );
    }

    // Generating state
    if (isGenerating) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-6">
                <div className="relative">
                    <Loader2 className="w-12 h-12 text-purple-600 animate-spin" />
                </div>
                <div className="space-y-2">
                    <p className="text-foreground font-medium">Generating podcast...</p>
                    <p className="text-sm text-muted-foreground max-w-xs">
                        Creating dialogue, synthesizing speech, and assembling audio.
                        This may take a few minutes.
                    </p>
                </div>
            </div>
        );
    }

    // Error state
    if (hasError && !hasContent) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-4">
                <div className="bg-red-50 dark:bg-red-900/20 p-4 rounded-full">
                    <AlertCircle className="w-8 h-8 text-red-600 dark:text-red-400" />
                </div>
                <p className="text-foreground font-medium">Error</p>
                <p className="text-sm text-muted-foreground max-w-xs">{loadError}</p>
                <button
                    onClick={clearError}
                    className="text-sm text-purple-600 dark:text-purple-400 hover:underline"
                >
                    Dismiss
                </button>
            </div>
        );
    }

    // Idle state - no content yet
    if (!hasContent) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-6">
                <div className="bg-purple-50 dark:bg-purple-900/20 p-6 rounded-full">
                    <Mic className="w-12 h-12 text-purple-600 dark:text-purple-400" />
                </div>
                <div className="max-w-xs space-y-2">
                    <h3 className="text-lg font-semibold text-foreground">Podcast</h3>
                    <p className="text-sm text-muted-foreground">
                        Generate a two-person dialogue podcast from lecture content,
                        similar to NotebookLM&apos;s Audio Overview.
                    </p>
                </div>
                <button
                    onClick={handleGenerate}
                    disabled={isGenerating}
                    className="inline-flex items-center gap-2 px-6 py-2.5 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors shadow-sm disabled:opacity-50"
                >
                    <Sparkles className="w-4 h-4" />
                    Generate Podcast
                </button>
            </div>
        );
    }

    // Content view: audio player + transcript
    return (
        <div className="flex flex-col h-full bg-background">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-card">
                <div className="flex items-center gap-2 min-w-0">
                    <Mic className="w-5 h-5 flex-shrink-0 text-purple-600 dark:text-purple-400" />
                    <div className="min-w-0">
                        <h3 className="font-semibold text-foreground truncate">{data?.title || "Podcast"}</h3>
                        {data?.updatedAt && (
                            <span className="text-xs text-muted-foreground">
                                {new Date(data.updatedAt).toLocaleDateString()}
                            </span>
                        )}
                    </div>
                </div>
                <button
                    onClick={handleGenerate}
                    disabled={isGenerating}
                    className="p-2 hover:bg-muted rounded-full transition-colors disabled:opacity-50"
                    title="Regenerate"
                >
                    <RefreshCw className="w-4 h-4 text-muted-foreground" />
                </button>
            </div>

            {/* Audio player controls */}
            {audioUrl && (
                <div className="px-4 py-3 border-b border-border bg-card/50">
                    {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
                    <audio
                        ref={audioRef}
                        src={audioUrl}
                        onTimeUpdate={handleTimeUpdate}
                        onLoadedMetadata={handleLoadedMetadata}
                        onEnded={handleAudioEnded}
                        preload="metadata"
                    />

                    {/* Progress bar */}
                    <div
                        className="w-full h-2 bg-muted rounded-full cursor-pointer mb-3 group"
                        onClick={handleProgressClick}
                    >
                        <div
                            className="h-full bg-purple-500 rounded-full transition-all duration-100 group-hover:bg-purple-600"
                            style={{ width: duration ? `${(currentTime / duration) * 100}%` : "0%" }}
                        />
                    </div>

                    {/* Controls row */}
                    <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground tabular-nums w-10">
                            {formatDuration(currentTime)}
                        </span>

                        <div className="flex items-center gap-2">
                            <button
                                onClick={skipBack}
                                className="p-1.5 hover:bg-muted rounded-full transition-colors"
                                title="Back 10s"
                            >
                                <SkipBack className="w-4 h-4 text-foreground" />
                            </button>
                            <button
                                onClick={togglePlayPause}
                                disabled={!audioReady}
                                className="p-2.5 bg-purple-600 hover:bg-purple-700 text-white rounded-full transition-colors disabled:opacity-50"
                            >
                                {isPlaying ? (
                                    <Pause className="w-5 h-5" />
                                ) : (
                                    <Play className="w-5 h-5 ml-0.5" />
                                )}
                            </button>
                            <button
                                onClick={skipForward}
                                className="p-1.5 hover:bg-muted rounded-full transition-colors"
                                title="Forward 10s"
                            >
                                <SkipForward className="w-4 h-4 text-foreground" />
                            </button>
                        </div>

                        <span className="text-xs text-muted-foreground tabular-nums w-10 text-right">
                            {formatDuration(duration)}
                        </span>
                    </div>
                </div>
            )}

            {/* Summary */}
            {data?.summary && (
                <div className="px-4 py-2 border-b border-border bg-muted/20">
                    <p className="text-xs text-muted-foreground leading-relaxed">{data.summary}</p>
                </div>
            )}

            {/* Transcript */}
            <div className="flex-1 overflow-y-auto p-4 space-y-1">
                {segments.map((segment, index) => (
                    <TranscriptSegment
                        key={index}
                        segment={segment}
                        isActive={index === activeSegmentIndex}
                        onSeek={seekTo}
                    />
                ))}
            </div>
        </div>
    );
}

// ─── Transcript Segment ────────────────────────────────────────

interface TranscriptSegmentProps {
    segment: PodcastSegment;
    isActive: boolean;
    onSeek: (time: number) => void;
}

function TranscriptSegment({ segment, isActive, onSeek }: TranscriptSegmentProps) {
    const segmentRef = useRef<HTMLButtonElement>(null);
    const isHost = segment.speaker === "host";

    // Auto-scroll active segment into view
    useEffect(() => {
        if (isActive && segmentRef.current) {
            segmentRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    }, [isActive]);

    return (
        <button
            ref={segmentRef}
            onClick={() => onSeek(segment.startTime)}
            className={cn(
                "w-full text-left px-3 py-2 rounded-lg transition-colors group",
                isActive
                    ? "bg-purple-50 dark:bg-purple-900/20 ring-1 ring-purple-200 dark:ring-purple-800"
                    : "hover:bg-muted/50"
            )}
        >
            <div className="flex items-start gap-2">
                {/* Speaker indicator */}
                <span
                    className={cn(
                        "flex-shrink-0 mt-0.5 w-2 h-2 rounded-full",
                        isHost
                            ? "bg-purple-500"
                            : "bg-teal-500"
                    )}
                />
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                        <span className={cn(
                            "text-xs font-semibold capitalize",
                            isHost
                                ? "text-purple-600 dark:text-purple-400"
                                : "text-teal-600 dark:text-teal-400"
                        )}>
                            {segment.speaker}
                        </span>
                        <span className="text-xs text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
                            {formatDuration(segment.startTime)}
                        </span>
                    </div>
                    <p className={cn(
                        "text-sm leading-relaxed",
                        isActive ? "text-foreground" : "text-muted-foreground"
                    )}>
                        {segment.text}
                    </p>
                </div>
            </div>
        </button>
    );
}

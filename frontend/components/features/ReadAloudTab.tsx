"use client";

/**
 * ReadAloudTab — Sentence-by-sentence TTS read-aloud of notes content.
 *
 * Features:
 * 1. Play/Pause/Stop controls with progress indicator.
 * 2. Paragraph headers with jump-to-play buttons.
 * 3. Sentence-level highlighting during playback.
 * 4. Auto-scroll to current sentence.
 */

import { useCallback, useRef, useEffect } from "react";
import {
    Volume2,
    Play,
    Pause,
    Square,
    Loader2,
    AlertCircle,
    SkipForward,
} from "lucide-react";
import { useLanguageSettings } from "@/stores/useGlobalSettingsStore";
import { useReadAloud, type ReadAloudState } from "@/hooks/useReadAloud";
import type { ReadAloudStreamParams, ReadAloudMeta } from "@/lib/api/readAloud";
import { cn } from "@/lib/utils";

interface ReadAloudTabProps {
    videoId: string;
}

export function ReadAloudTab({ videoId }: ReadAloudTabProps) {
    const { original: sourceLanguage, translated: targetLanguage } = useLanguageSettings();

    const {
        state,
        meta,
        sentences,
        currentIndex,
        totalSentences,
        readySentences,
        error,
        play,
        pause,
        resume,
        stop,
        jumpToParagraph,
    } = useReadAloud();

    const buildParams = useCallback(
        (): ReadAloudStreamParams => ({
            contentId: videoId,
            targetLanguage: targetLanguage || "en",
            sourceLanguage: sourceLanguage || undefined,
        }),
        [videoId, targetLanguage, sourceLanguage]
    );

    const handlePlay = useCallback(() => {
        play(buildParams());
    }, [play, buildParams]);

    const handleToggle = useCallback(() => {
        if (state === "idle" || state === "loading") {
            handlePlay();
        } else if (state === "playing") {
            pause();
        } else if (state === "paused") {
            resume();
        }
    }, [state, handlePlay, pause, resume]);

    const handleJumpToParagraph = useCallback(
        (paragraphIndex: number) => {
            jumpToParagraph(buildParams(), paragraphIndex);
        },
        [jumpToParagraph, buildParams]
    );

    const isActive = state !== "idle";
    const progress = totalSentences > 0 ? ((currentIndex + 1) / totalSentences) * 100 : 0;

    // ─── Idle state ──────────────────────────────────────────
    if (state === "idle" && !error && sentences.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-6">
                <div className="bg-emerald-50 dark:bg-emerald-900/20 p-6 rounded-full">
                    <Volume2 className="w-12 h-12 text-emerald-600 dark:text-emerald-400" />
                </div>
                <div className="max-w-xs space-y-2">
                    <h3 className="text-lg font-semibold text-foreground">Read Aloud</h3>
                    <p className="text-sm text-muted-foreground">
                        Listen to your notes read aloud sentence by sentence.
                        Supports translation to a different language.
                    </p>
                </div>
                <button
                    onClick={handlePlay}
                    className="inline-flex items-center gap-2 px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium transition-colors shadow-sm"
                >
                    <Play className="w-4 h-4" />
                    Start Read Aloud
                </button>
            </div>
        );
    }

    // ─── Error state ─────────────────────────────────────────
    if (error && sentences.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-4">
                <div className="bg-red-50 dark:bg-red-900/20 p-4 rounded-full">
                    <AlertCircle className="w-8 h-8 text-red-600 dark:text-red-400" />
                </div>
                <p className="text-foreground font-medium">Error</p>
                <p className="text-sm text-muted-foreground max-w-xs">{error}</p>
                <button
                    onClick={handlePlay}
                    className="text-sm text-emerald-600 dark:text-emerald-400 hover:underline"
                >
                    Try again
                </button>
            </div>
        );
    }

    // ─── Active / Content state ──────────────────────────────
    return (
        <div className="flex flex-col h-full bg-background">
            {/* Header + Controls */}
            <div className="px-4 py-3 border-b border-border bg-card">
                {/* Controls row */}
                <div className="flex items-center gap-3">
                    {/* Play/Pause */}
                    <button
                        onClick={handleToggle}
                        className="p-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-full transition-colors disabled:opacity-50"
                        disabled={state === "loading"}
                    >
                        {state === "loading" ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                        ) : state === "playing" ? (
                            <Pause className="w-4 h-4" />
                        ) : (
                            <Play className="w-4 h-4 ml-0.5" />
                        )}
                    </button>

                    {/* Stop */}
                    {isActive && (
                        <button
                            onClick={stop}
                            className="p-2 hover:bg-muted rounded-full transition-colors"
                            title="Stop"
                        >
                            <Square className="w-4 h-4 text-foreground" />
                        </button>
                    )}

                    {/* Progress info */}
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                            <span>
                                {state === "loading"
                                    ? "Preparing..."
                                    : currentIndex >= 0
                                      ? `Sentence ${currentIndex + 1} / ${totalSentences}`
                                      : "Ready"}
                            </span>
                            <span>{readySentences} / {totalSentences} synthesized</span>
                        </div>

                        {/* Progress bar */}
                        <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
                            <div
                                className="h-full bg-emerald-500 rounded-full transition-all duration-300"
                                style={{ width: `${progress}%` }}
                            />
                        </div>
                    </div>
                </div>
            </div>

            {/* Sentence list with paragraph headers */}
            <SentenceList
                meta={meta}
                sentences={sentences}
                currentIndex={currentIndex}
                state={state}
                onJumpToParagraph={handleJumpToParagraph}
            />
        </div>
    );
}

// ─── Sentence List ───────────────────────────────────────────

interface SentenceItem {
    paragraphIndex: number;
    sentenceIndex: number;
    sentenceKey: string;
    originalText: string;
    spokenText: string;
    audioUrl: string;
}

interface SentenceListProps {
    meta: ReadAloudMeta | null;
    sentences: SentenceItem[];
    currentIndex: number;
    state: ReadAloudState;
    onJumpToParagraph: (index: number) => void;
}

function SentenceList({ meta, sentences, currentIndex, state, onJumpToParagraph }: SentenceListProps) {
    const activeRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to active sentence
    useEffect(() => {
        if (activeRef.current && state === "playing") {
            activeRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    }, [currentIndex, state]);

    if (!meta) {
        return (
            <div className="flex-1 flex items-center justify-center">
                <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
            </div>
        );
    }

    // Group sentences by paragraph
    const paragraphMap = new Map<number, typeof sentences>();
    const sentenceIndexByKey = new Map<string, number>();
    for (const s of sentences) {
        sentenceIndexByKey.set(s.sentenceKey, sentenceIndexByKey.size);
        const group = paragraphMap.get(s.paragraphIndex) ?? [];
        group.push(s);
        paragraphMap.set(s.paragraphIndex, group);
    }

    return (
        <div className="flex-1 overflow-y-auto">
            {meta.paragraphs.map((para) => {
                const paraSentences = paragraphMap.get(para.index) ?? [];

                return (
                    <div key={para.index} className="border-b border-border last:border-b-0">
                        {/* Paragraph header */}
                        <div className="flex items-center gap-2 px-4 py-2 bg-muted/30 sticky top-0 z-10">
                            <button
                                onClick={() => onJumpToParagraph(para.index)}
                                className="p-1 hover:bg-emerald-100 dark:hover:bg-emerald-900/30 rounded transition-colors"
                                title={`Play from paragraph ${para.index + 1}`}
                            >
                                <SkipForward className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                            </button>
                            <span className="text-xs font-medium text-foreground truncate">
                                {para.title || `Paragraph ${para.index + 1}`}
                            </span>
                            <span className="text-xs text-muted-foreground ml-auto whitespace-nowrap">
                                {paraSentences.length} / {para.sentenceCount}
                            </span>
                        </div>

                        {/* Sentences */}
                        <div className="px-4 py-1">
                            {paraSentences.map((sentence) => {
                                const globalIndex = sentenceIndexByKey.get(sentence.sentenceKey) ?? -1;
                                const isActive = globalIndex === currentIndex;
                                const isPast = globalIndex < currentIndex;

                                return (
                                    <div
                                        key={sentence.sentenceKey}
                                        ref={isActive ? activeRef : null}
                                        className={cn(
                                            "py-1.5 px-2 rounded text-sm leading-relaxed transition-colors",
                                            isActive
                                                ? "bg-emerald-50 dark:bg-emerald-900/20 text-foreground font-medium"
                                                : isPast
                                                  ? "text-muted-foreground"
                                                  : "text-foreground/80"
                                        )}
                                    >
                                        {sentence.spokenText}
                                    </div>
                                );
                            })}

                            {/* Placeholder for pending sentences */}
                            {paraSentences.length < para.sentenceCount && (
                                <div className="py-1.5 px-2 flex items-center gap-1.5 text-xs text-muted-foreground">
                                    <Loader2 className="w-3 h-3 animate-spin" />
                                    <span>
                                        Synthesizing... ({para.sentenceCount - paraSentences.length} remaining)
                                    </span>
                                </div>
                            )}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

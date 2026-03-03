"use client";

/**
 * FlashcardTab — AI-generated active-recall flashcards.
 *
 * Two view modes:
 * 1. Flip-card flow: One card at a time, tap to reveal, navigate with arrows.
 * 2. List browse: Scrollable list of all cards.
 *
 * Cards have an optional video timestamp for seeking.
 */

import { useState, useCallback, type KeyboardEvent, type MouseEvent } from "react";
import {
    CreditCard,
    RefreshCw,
    AlertCircle,
    Loader2,
    Sparkles,
    ChevronLeft,
    ChevronRight,
    List,
    Layers,
    ExternalLink,
    RotateCcw,
} from "lucide-react";
import { getFlashcard, generateFlashcard } from "@/lib/api/flashcard";
import type { FlashcardItem } from "@/lib/api/flashcard";
import { useLanguageSettings, useNoteSettings } from "@/stores/useGlobalSettingsStore";
import { logger } from "@/shared/infrastructure";
import { useSSEGenerationRetry } from "@/hooks/useSSEGenerationRetry";
import { cn } from "@/lib/utils";
import { formatTime } from "@/lib/timeFormat";

const log = logger.scope("FlashcardTab");

type ViewMode = "flip" | "list";

interface FlashcardTabProps {
    videoId: string;
    onSeek: (time: number) => void;
    refreshTrigger: number;
}

interface FlashcardData {
    items: FlashcardItem[];
    updatedAt: string | null;
}

function hasActiveSelectionWithin(element: HTMLElement): boolean {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed || selection.rangeCount === 0) {
        return false;
    }

    const range = selection.getRangeAt(0);
    return element.contains(range.commonAncestorContainer);
}

export function FlashcardTab({ videoId, onSeek, refreshTrigger }: FlashcardTabProps) {
    const { translated: language } = useLanguageSettings();
    const noteSettings = useNoteSettings();
    const [viewMode, setViewMode] = useState<ViewMode>("flip");
    const [currentIndex, setCurrentIndex] = useState(0);
    const [flipped, setFlipped] = useState(false);

    const fetchContent = useCallback(async (): Promise<FlashcardData | null> => {
        const result = await getFlashcard(videoId, language || "en");
        if (result && result.items.length > 0) {
            return { items: result.items, updatedAt: result.updatedAt };
        }
        return null;
    }, [videoId, language]);

    const submitGeneration = useCallback(async () => {
        return await generateFlashcard({
            contentId: videoId,
            language: language || "en",
            contextMode: noteSettings.contextMode,
            minCriticality: "low",
            subjectType: "auto",
        });
    }, [videoId, language, noteSettings.contextMode]);

    const { data, loading, loadError, isGenerating, clearError, handleGenerate } =
        useSSEGenerationRetry<FlashcardData>({
            contentId: videoId,
            refreshTrigger,
            fetchContent,
            submitGeneration,
            log,
            extraDeps: [language],
            taskType: "flashcard_generation",
        });

    const items = data?.items ?? [];
    const updatedAt = data?.updatedAt ?? null;

    const handleNext = useCallback(() => {
        setFlipped(false);
        setCurrentIndex((prev) => Math.min(prev + 1, items.length));
    }, [items.length]);

    const handlePrev = useCallback(() => {
        setFlipped(false);
        setCurrentIndex((prev) => Math.max(prev - 1, 0));
    }, []);

    const handleFlip = useCallback(() => {
        setFlipped((prev) => !prev);
    }, []);

    const handleRestart = useCallback(() => {
        setCurrentIndex(0);
        setFlipped(false);
    }, []);

    const handleGenerateAndReset = useCallback(() => {
        setCurrentIndex(0);
        setFlipped(false);
        handleGenerate();
    }, [handleGenerate]);

    const hasContent = items.length > 0;
    const hasError = loadError !== null;
    const isComplete = currentIndex >= items.length;

    // Loading state
    if (loading && !hasContent) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-6">
                <Loader2 className="w-8 h-8 text-sky-600 animate-spin" />
                <p className="text-sm text-muted-foreground">Loading flashcards...</p>
            </div>
        );
    }

    // Generating state
    if (isGenerating) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-6">
                <div className="relative">
                    <Loader2 className="w-12 h-12 text-sky-600 animate-spin" />
                </div>
                <div className="space-y-2">
                    <p className="text-foreground font-medium">Generating flashcards...</p>
                    <p className="text-sm text-muted-foreground max-w-xs">
                        Creating active-recall cards from lecture content.
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
                    className="text-sm text-sky-600 dark:text-sky-400 hover:underline"
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
                <div className="bg-sky-50 dark:bg-sky-900/20 p-6 rounded-full">
                    <CreditCard className="w-12 h-12 text-sky-600 dark:text-sky-400" />
                </div>
                <div className="max-w-xs space-y-2">
                    <h3 className="text-lg font-semibold text-foreground">Flashcards</h3>
                    <p className="text-sm text-muted-foreground">
                        Generate active-recall flashcards to test your understanding of key concepts from the lecture.
                    </p>
                </div>
                <button
                    onClick={handleGenerate}
                    disabled={isGenerating}
                    className="inline-flex items-center gap-2 px-6 py-2.5 bg-sky-600 hover:bg-sky-700 text-white rounded-lg font-medium transition-colors shadow-sm disabled:opacity-50"
                >
                    <Sparkles className="w-4 h-4" />
                    Generate Flashcards
                </button>
            </div>
        );
    }

    // Content view
    return (
        <div className="flex flex-col h-full bg-background">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-card">
                <div className="flex items-center gap-2">
                    <CreditCard className="w-5 h-5 text-sky-600 dark:text-sky-400" />
                    <h3 className="font-semibold text-foreground">Flashcards</h3>
                    <span className="text-xs text-muted-foreground">
                        {items.length} cards
                    </span>
                    {updatedAt && (
                        <span className="text-xs text-muted-foreground">
                            · {new Date(updatedAt).toLocaleDateString()}
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-1">
                    {/* View mode toggle */}
                    <button
                        onClick={() => { setViewMode("flip"); setCurrentIndex(0); setFlipped(false); }}
                        className={cn(
                            "p-2 rounded-full transition-colors",
                            viewMode === "flip" ? "bg-sky-100 dark:bg-sky-900/30 text-sky-700 dark:text-sky-300" : "hover:bg-muted text-muted-foreground"
                        )}
                        title="Flip card view"
                    >
                        <Layers className="w-4 h-4" />
                    </button>
                    <button
                        onClick={() => setViewMode("list")}
                        className={cn(
                            "p-2 rounded-full transition-colors",
                            viewMode === "list" ? "bg-sky-100 dark:bg-sky-900/30 text-sky-700 dark:text-sky-300" : "hover:bg-muted text-muted-foreground"
                        )}
                        title="List view"
                    >
                        <List className="w-4 h-4" />
                    </button>
                    <button
                        onClick={handleGenerateAndReset}
                        disabled={isGenerating}
                        className="p-2 hover:bg-muted rounded-full transition-colors disabled:opacity-50"
                        title="Regenerate"
                    >
                        <RefreshCw className="w-4 h-4 text-muted-foreground" />
                    </button>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto">
                {viewMode === "flip" ? (
                    <FlipCardView
                        items={items}
                        currentIndex={currentIndex}
                        flipped={flipped}
                        isComplete={isComplete}
                        onFlip={handleFlip}
                        onNext={handleNext}
                        onPrev={handlePrev}
                        onRestart={handleRestart}
                        onSeek={onSeek}
                    />
                ) : (
                    <ListView items={items} onSeek={onSeek} />
                )}
            </div>
        </div>
    );
}

// ─── Flip Card View ──────────────────────────────────────────────

interface FlipCardViewProps {
    items: FlashcardItem[];
    currentIndex: number;
    flipped: boolean;
    isComplete: boolean;
    onFlip: () => void;
    onNext: () => void;
    onPrev: () => void;
    onRestart: () => void;
    onSeek: (time: number) => void;
}

function FlipCardView({
    items,
    currentIndex,
    flipped,
    isComplete,
    onFlip,
    onNext,
    onPrev,
    onRestart,
    onSeek,
}: FlipCardViewProps) {
    if (isComplete) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-4">
                <div className="bg-sky-50 dark:bg-sky-900/20 p-4 rounded-full">
                    <CreditCard className="w-10 h-10 text-sky-600 dark:text-sky-400" />
                </div>
                <p className="text-lg font-bold text-sky-700 dark:text-sky-300">
                    All {items.length} cards reviewed!
                </p>
                <p className="text-sm text-muted-foreground">
                    Great job completing this deck.
                </p>
                <button
                    onClick={onRestart}
                    className="inline-flex items-center gap-2 px-4 py-2 text-sm bg-sky-600 hover:bg-sky-700 text-white rounded-lg font-medium transition-colors"
                >
                    <RotateCcw className="w-4 h-4" />
                    Start Over
                </button>
            </div>
        );
    }

    const card = items[currentIndex];

    const handleCardKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onFlip();
        }
    };
    const handleCardClick = (event: MouseEvent<HTMLDivElement>) => {
        if (hasActiveSelectionWithin(event.currentTarget)) {
            return;
        }
        onFlip();
    };

    return (
        <div className="flex flex-col h-full p-4">
            {/* Progress */}
            <div className="flex items-center justify-between mb-3">
                <span className="text-xs text-muted-foreground">
                    {currentIndex + 1} / {items.length}
                </span>
                <div className="flex-1 mx-3 h-1.5 bg-muted rounded-full overflow-hidden">
                    <div
                        className="h-full bg-sky-500 rounded-full transition-all duration-300"
                        style={{ width: `${((currentIndex + 1) / items.length) * 100}%` }}
                    />
                </div>
                {card.sourceCategory && (
                    <span className="text-xs text-muted-foreground capitalize">
                        {card.sourceCategory}
                    </span>
                )}
            </div>

            {/* Card */}
            <div
                role="button"
                tabIndex={0}
                aria-pressed={flipped}
                onClick={handleCardClick}
                onKeyDown={handleCardKeyDown}
                className={cn(
                    "flex-1 min-h-[200px] rounded-xl border-2 p-6 text-left transition-all cursor-pointer select-text",
                    "flex flex-col items-center justify-center",
                    flipped
                        ? "border-sky-300 dark:border-sky-700 bg-sky-50/50 dark:bg-sky-900/10"
                        : "border-border bg-card hover:border-sky-200 dark:hover:border-sky-800"
                )}
            >
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                    {flipped ? "Answer" : "Question"}
                </span>
                <p className={cn(
                    "text-center leading-relaxed",
                    flipped ? "text-sm text-foreground" : "text-base font-medium text-foreground"
                )}>
                    {flipped ? card.back : card.front}
                </p>
                {!flipped && (
                    <span className="mt-4 text-xs text-muted-foreground">
                        Tap to reveal answer
                    </span>
                )}
            </div>

            {/* Navigation + Timestamp */}
            <div className="flex items-center justify-between mt-3">
                <button
                    onClick={onPrev}
                    disabled={currentIndex === 0}
                    className="p-2 hover:bg-muted rounded-full transition-colors disabled:opacity-30"
                >
                    <ChevronLeft className="w-5 h-5" />
                </button>

                {card.sourceTimestamp != null && (
                    <button
                        onClick={() => onSeek(card.sourceTimestamp!)}
                        className="inline-flex items-center gap-1 text-xs text-sky-600 dark:text-sky-400 hover:underline"
                        title="Jump to this moment in video"
                    >
                        <ExternalLink className="w-3 h-3" />
                        {formatTime(card.sourceTimestamp!)}
                    </button>
                )}

                <button
                    onClick={onNext}
                    className="p-2 hover:bg-muted rounded-full transition-colors"
                >
                    <ChevronRight className="w-5 h-5" />
                </button>
            </div>
        </div>
    );
}

// ─── List View ───────────────────────────────────────────────────

interface ListViewProps {
    items: FlashcardItem[];
    onSeek: (time: number) => void;
}

function ListView({ items, onSeek }: ListViewProps) {
    return (
        <div className="p-4 space-y-4">
            {items.map((item, index) => (
                <ListCard key={index} item={item} index={index} onSeek={onSeek} />
            ))}
        </div>
    );
}

function ListCard({
    item,
    index,
    onSeek,
}: {
    item: FlashcardItem;
    index: number;
    onSeek: (time: number) => void;
}) {
    const [expanded, setExpanded] = useState(false);
    const handleToggleExpanded = () => {
        setExpanded((prev) => !prev);
    };
    const handleCardKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            handleToggleExpanded();
        }
    };
    const handleCardClick = (event: MouseEvent<HTMLDivElement>) => {
        if (hasActiveSelectionWithin(event.currentTarget)) {
            return;
        }
        handleToggleExpanded();
    };

    return (
        <div className="rounded-lg border border-border bg-card overflow-hidden">
            {/* Front (question) - always visible */}
            <div
                role="button"
                tabIndex={0}
                aria-expanded={expanded}
                onClick={handleCardClick}
                onKeyDown={handleCardKeyDown}
                className="w-full text-left p-4 hover:bg-accent/50 transition-colors select-text cursor-pointer"
            >
                <div className="flex items-start gap-2">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-sky-100 dark:bg-sky-900/30 text-sky-700 dark:text-sky-300 text-xs font-bold flex items-center justify-center mt-0.5">
                        {index + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-foreground">{item.front}</p>
                        <div className="flex items-center gap-2 mt-1">
                            {item.sourceCategory && (
                                <span className="text-xs text-muted-foreground capitalize">
                                    {item.sourceCategory}
                                </span>
                            )}
                            {item.sourceTimestamp != null && (
                                <button
                                    onClick={(e) => { e.stopPropagation(); onSeek(item.sourceTimestamp!); }}
                                    className="inline-flex items-center gap-1 text-xs text-sky-600 dark:text-sky-400 hover:underline"
                                >
                                    <ExternalLink className="w-3 h-3" />
                                    {formatTime(item.sourceTimestamp!)}
                                </button>
                            )}
                        </div>
                    </div>
                    <span className="text-xs text-muted-foreground mt-1">
                        {expanded ? "▲" : "▼"}
                    </span>
                </div>
            </div>

            {/* Back (answer) - expandable */}
            {expanded && (
                <div className="px-4 pb-4 pt-0 ml-8 border-t border-border mt-0">
                    <div className="pt-3">
                        <p className="text-xs font-semibold text-muted-foreground mb-1">Answer</p>
                        <p className="text-sm text-foreground leading-relaxed">{item.back}</p>
                    </div>
                </div>
            )}
        </div>
    );
}

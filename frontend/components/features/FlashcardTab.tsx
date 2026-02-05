"use client";

/**
 * FlashcardTab
 *
 * Displays saved vocabulary words with ability to delete.
 * This is a minimal implementation - spaced repetition review
 * can be added in a future iteration.
 */

import { memo, useCallback } from "react";
import { Trash2, BookOpen, ExternalLink } from "lucide-react";
import { useVocabularyStore, useVocabulary } from "@/stores/useVocabularyStore";
import type { VocabularyItem } from "@/lib/dictionary/types";
import { cn } from "@/lib/utils";
import { formatTime } from "@/lib/timeFormat";

interface FlashcardTabProps {
    /** Current video ID for filtering */
    videoId?: string;
    /** Callback when user wants to seek to timestamp */
    onSeek?: (time: number) => void;
    /** Show all vocabulary or filter by current video */
    showAll?: boolean;
}

function VocabularyCard({
    item,
    onDelete,
    onSeek,
}: {
    item: VocabularyItem;
    onDelete: () => void;
    onSeek?: (time: number) => void;
}) {
    const handleSeek = useCallback(() => {
        if (onSeek) {
            onSeek(item.context.timestamp);
        }
    }, [onSeek, item.context.timestamp]);

    return (
        <div className="p-3 border border-border rounded-lg bg-card hover:bg-accent/50 transition-colors">
            <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        <span className="font-semibold text-foreground">
                            {item.word}
                        </span>
                        {item.phonetic && (
                            <span className="text-sm text-muted-foreground">
                                {item.phonetic}
                            </span>
                        )}
                    </div>
                    <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                        {item.definition}
                    </p>
                </div>
                <button
                    onClick={onDelete}
                    className="p-1.5 text-muted-foreground hover:text-destructive rounded transition-colors"
                    title="Remove from vocabulary"
                >
                    <Trash2 className="w-4 h-4" />
                </button>
            </div>

            {/* Context */}
            {item.context.sentence && (
                <div className="mt-2 pt-2 border-t border-border">
                    <p className="text-xs text-muted-foreground italic line-clamp-1">
                        "{item.context.sentence}"
                    </p>
                    {onSeek && (
                        <button
                            onClick={handleSeek}
                            className="mt-1 text-xs text-blue-500 hover:text-blue-600 flex items-center gap-1"
                            title="Jump to this moment in video"
                        >
                            <ExternalLink className="w-3 h-3" />
                            {formatTime(item.context.timestamp)}
                        </button>
                    )}
                </div>
            )}
        </div>
    );
}

function FlashcardTabBase({ videoId, onSeek, showAll = false }: FlashcardTabProps) {
    const { items, hydrated, remove } = useVocabulary();
    const getByVideo = useVocabularyStore((state) => state.getByVideo);

    // Filter items based on showAll flag
    const displayItems = showAll
        ? items
        : videoId
          ? getByVideo(videoId)
          : items;

    const handleDelete = useCallback(
        (word: string, locale: string) => {
            remove(word, locale);
        },
        [remove]
    );

    if (!hydrated) {
        return (
            <div className="flex items-center justify-center h-32 text-muted-foreground">
                Loading vocabulary...
            </div>
        );
    }

    if (displayItems.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-32 text-muted-foreground">
                <BookOpen className="w-8 h-8 mb-2 opacity-50" />
                <p className="text-sm">No saved words yet</p>
                <p className="text-xs mt-1">
                    Hover over words in subtitles to look them up
                </p>
            </div>
        );
    }

    return (
        <div className="p-4 space-y-3 overflow-y-auto max-h-full">
            <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-medium text-foreground">
                    Vocabulary ({displayItems.length})
                </h3>
            </div>

            <div className="space-y-2">
                {displayItems.map((item) => (
                    <VocabularyCard
                        key={item.id}
                        item={item}
                        onDelete={() => handleDelete(item.word, item.locale)}
                        onSeek={onSeek}
                    />
                ))}
            </div>
        </div>
    );
}

export const FlashcardTab = memo(FlashcardTabBase);

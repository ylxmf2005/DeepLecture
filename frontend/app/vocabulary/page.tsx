"use client";

/**
 * Vocabulary Page
 *
 * Dedicated page to view all saved vocabulary words across all videos.
 */

import { useCallback } from "react";
import { BookOpen, Trash2 } from "lucide-react";
import { useVocabulary } from "@/stores/useVocabularyStore";

export default function VocabularyPage() {
    const { items, hydrated, remove } = useVocabulary();

    const handleDelete = useCallback(
        (word: string, locale: string) => {
            remove(word, locale);
        },
        [remove]
    );

    return (
        <div className="container mx-auto py-8 px-4 max-w-4xl">
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-foreground">Vocabulary</h1>
                <p className="text-muted-foreground mt-1">
                    All words you&apos;ve saved while watching videos
                </p>
            </div>

            <div className="bg-card border border-border rounded-lg p-4">
                {!hydrated ? (
                    <div className="flex items-center justify-center h-32 text-muted-foreground">
                        Loading vocabulary...
                    </div>
                ) : items.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-32 text-muted-foreground">
                        <BookOpen className="w-8 h-8 mb-2 opacity-50" />
                        <p className="text-sm">No saved words yet</p>
                        <p className="text-xs mt-1">
                            Hover over words in subtitles to look them up
                        </p>
                    </div>
                ) : (
                    <div className="space-y-2">
                        <h3 className="text-sm font-medium text-foreground mb-3">
                            Vocabulary ({items.length})
                        </h3>
                        {items.map((item) => (
                            <div
                                key={item.id}
                                className="p-3 border border-border rounded-lg bg-card hover:bg-accent/50 transition-colors"
                            >
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
                                        onClick={() => handleDelete(item.word, item.locale)}
                                        className="p-1.5 text-muted-foreground hover:text-destructive rounded transition-colors"
                                        title="Remove from vocabulary"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

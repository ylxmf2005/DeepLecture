"use client";

/**
 * Vocabulary Page
 *
 * Dedicated page to view all saved vocabulary words across all videos.
 */

import { FlashcardTab } from "@/components/features/FlashcardTab";

export default function VocabularyPage() {
    return (
        <div className="container mx-auto py-8 px-4 max-w-4xl">
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-foreground">Vocabulary</h1>
                <p className="text-muted-foreground mt-1">
                    All words you've saved while watching videos
                </p>
            </div>

            <div className="bg-card border border-border rounded-lg">
                <FlashcardTab showAll />
            </div>
        </div>
    );
}

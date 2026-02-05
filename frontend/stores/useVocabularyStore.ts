"use client";

/**
 * Vocabulary Store
 *
 * Persists user's saved vocabulary items with localStorage
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { VocabularyItem } from "@/lib/dictionary/types";

interface VocabularyState {
    items: VocabularyItem[];
    _hydrated: boolean;
}

interface VocabularyActions {
    /**
     * Add a word to the vocabulary
     */
    add: (item: Omit<VocabularyItem, "id" | "savedAt">) => void;

    /**
     * Remove a word from the vocabulary
     */
    remove: (word: string, locale: string) => void;

    /**
     * Check if a word is already saved
     */
    has: (word: string, locale: string) => boolean;

    /**
     * Get all items for a specific video
     */
    getByVideo: (videoId: string) => VocabularyItem[];

    /**
     * Clear all vocabulary items
     */
    clear: () => void;
}

type VocabularyStore = VocabularyState & VocabularyActions;

/**
 * Generate unique ID for vocabulary item
 */
function generateId(): string {
    return `vocab-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/**
 * Normalize word for comparison
 */
function normalizeWord(word: string): string {
    return word.toLowerCase().trim();
}

export const useVocabularyStore = create<VocabularyStore>()(
    persist(
        (set, get) => ({
            items: [],
            _hydrated: false,

            add: (item) => {
                const normalizedWord = normalizeWord(item.word);

                // Check if already exists
                const exists = get().items.some(
                    (i) =>
                        normalizeWord(i.word) === normalizedWord &&
                        i.locale === item.locale
                );

                if (exists) {
                    return;
                }

                const newItem: VocabularyItem = {
                    ...item,
                    word: normalizedWord,
                    id: generateId(),
                    savedAt: new Date().toISOString(),
                };

                set((state) => ({
                    items: [newItem, ...state.items],
                }));
            },

            remove: (word, locale) => {
                const normalizedWord = normalizeWord(word);
                set((state) => ({
                    items: state.items.filter(
                        (i) =>
                            !(normalizeWord(i.word) === normalizedWord && i.locale === locale)
                    ),
                }));
            },

            has: (word, locale) => {
                const normalizedWord = normalizeWord(word);
                return get().items.some(
                    (i) =>
                        normalizeWord(i.word) === normalizedWord && i.locale === locale
                );
            },

            getByVideo: (videoId) => {
                return get().items.filter((i) => i.context.videoId === videoId);
            },

            clear: () => {
                set({ items: [] });
            },
        }),
        {
            name: "deeplecture-vocabulary",
            storage: createJSONStorage(() => localStorage),
            version: 1,
            onRehydrateStorage: () => (_state, error) => {
                if (!error) {
                    useVocabularyStore.setState({ _hydrated: true });
                }
            },
        }
    )
);

/**
 * Hook to get vocabulary items with hydration status
 */
export function useVocabulary() {
    const items = useVocabularyStore((state) => state.items);
    const hydrated = useVocabularyStore((state) => state._hydrated);
    const add = useVocabularyStore((state) => state.add);
    const remove = useVocabularyStore((state) => state.remove);
    const has = useVocabularyStore((state) => state.has);

    return { items, hydrated, add, remove, has };
}

/**
 * Dictionary types for the language learning feature
 */

/**
 * A single definition with part of speech and example
 */
export interface Definition {
    partOfSpeech: string;
    meaning: string;
    example?: string;
}

/**
 * Dictionary entry returned from lookup
 */
export interface DictionaryEntry {
    word: string;
    phonetic?: string;
    definitions: Definition[];
    examples: string[];
    source: "api" | "cache";
}

/**
 * Provider interface for dictionary lookups
 * Allows swapping between different dictionary sources
 */
export interface DictionaryProvider {
    /**
     * Check if this provider supports lookups for the given locale
     */
    supports(locale: string): boolean;

    /**
     * Look up a word in the dictionary
     * @param word - The word to look up
     * @param locale - The locale/language code (e.g., "en", "en-US")
     * @param signal - Optional AbortSignal for cancellation
     * @returns The dictionary entry, or null if not found/unsupported
     */
    lookup(
        word: string,
        locale: string,
        signal?: AbortSignal
    ): Promise<DictionaryEntry | null>;
}

/**
 * Token from word tokenization
 */
export interface Token {
    /** The raw text of this token */
    text: string;
    /** Whether this token is a word (vs punctuation/whitespace) */
    isWord: boolean;
    /** Normalized form (lowercase, trimmed) */
    normalized: string;
    /** Start index in the original string */
    start: number;
    /** End index in the original string (exclusive) */
    end: number;
}

/**
 * Vocabulary item saved by user
 */
export interface VocabularyItem {
    id: string;
    word: string;
    locale: string;
    definition: string;
    phonetic?: string;
    context: {
        videoId: string;
        timestamp: number;
        sentence: string;
    };
    savedAt: string;
}

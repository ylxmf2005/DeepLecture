/**
 * Dictionary lookup with Free Dictionary API and in-memory caching
 */

import type { DictionaryEntry, DictionaryProvider, Definition } from "./types";

// Re-export types for convenience
export type { DictionaryEntry, DictionaryProvider };

// Supported languages (Free Dictionary API supports these)
const SUPPORTED_LOCALES = new Set([
    "en",
    "en-US",
    "en-GB",
    "en-AU",
    "en-CA",
    "en-NZ",
]);

// In-memory cache for lookups
const cache = new Map<string, DictionaryEntry>();

/**
 * Generate cache key from word and locale
 */
function getCacheKey(word: string, locale: string): string {
    const normalizedWord = word.toLowerCase().trim();
    const baseLocale = locale.split("-")[0]; // "en-US" -> "en"
    return `${baseLocale}:${normalizedWord}`;
}

/**
 * Check if locale is supported
 */
function isSupported(locale: string): boolean {
    const baseLocale = locale.split("-")[0];
    return SUPPORTED_LOCALES.has(locale) || SUPPORTED_LOCALES.has(baseLocale);
}

/**
 * Free Dictionary API response types
 */
interface FreeDictApiDefinition {
    definition: string;
    example?: string;
}

interface FreeDictApiMeaning {
    partOfSpeech: string;
    definitions: FreeDictApiDefinition[];
}

interface FreeDictApiResponse {
    word: string;
    phonetic?: string;
    phonetics?: Array<{ text?: string; audio?: string }>;
    meanings: FreeDictApiMeaning[];
}

/**
 * Parse Free Dictionary API response into our DictionaryEntry format
 */
function parseApiResponse(data: FreeDictApiResponse[]): DictionaryEntry | null {
    if (!data || data.length === 0) {
        return null;
    }

    const first = data[0];

    // Extract phonetic - try main phonetic first, then phonetics array
    let phonetic = first.phonetic;
    if (!phonetic && first.phonetics?.length) {
        phonetic = first.phonetics.find((p) => p.text)?.text;
    }

    // Extract definitions
    const definitions: Definition[] = [];
    const examples: string[] = [];

    for (const meaning of first.meanings) {
        for (const def of meaning.definitions) {
            definitions.push({
                partOfSpeech: meaning.partOfSpeech,
                meaning: def.definition,
                example: def.example,
            });

            if (def.example) {
                examples.push(def.example);
            }
        }
    }

    return {
        word: first.word,
        phonetic,
        definitions,
        examples,
        source: "api",
    };
}

/**
 * Fetch word definition from Free Dictionary API
 */
async function fetchFromApi(
    word: string,
    locale: string,
    signal?: AbortSignal
): Promise<DictionaryEntry | null> {
    const baseLocale = locale.split("-")[0];
    const url = `https://api.dictionaryapi.dev/api/v2/entries/${baseLocale}/${encodeURIComponent(word)}`;

    try {
        const response = await fetch(url, { signal });

        if (!response.ok) {
            return null;
        }

        const data = (await response.json()) as FreeDictApiResponse[];
        return parseApiResponse(data);
    } catch (error) {
        // Network error or aborted
        if (error instanceof Error && error.name === "AbortError") {
            // Request was cancelled, don't log
        }
        return null;
    }
}

/**
 * Create a dictionary lookup provider with caching
 *
 * @returns DictionaryProvider instance
 *
 * @example
 * ```ts
 * const provider = createDictionaryLookup();
 *
 * if (provider.supports("en")) {
 *   const entry = await provider.lookup("hello", "en");
 *   console.log(entry?.phonetic); // "/həˈloʊ/"
 * }
 * ```
 */
export function createDictionaryLookup(): DictionaryProvider {
    return {
        supports(locale: string): boolean {
            return isSupported(locale);
        },

        async lookup(
            word: string,
            locale: string,
            signal?: AbortSignal
        ): Promise<DictionaryEntry | null> {
            // Check locale support
            if (!isSupported(locale)) {
                return null;
            }

            // Normalize word
            const normalizedWord = word.toLowerCase().trim();
            if (!normalizedWord) {
                return null;
            }

            // Check cache
            const cacheKey = getCacheKey(normalizedWord, locale);
            const cached = cache.get(cacheKey);
            if (cached) {
                return { ...cached, source: "cache" };
            }

            // Fetch from API
            const entry = await fetchFromApi(normalizedWord, locale, signal);

            // Cache successful lookups only
            if (entry) {
                cache.set(cacheKey, entry);
            }

            return entry;
        },
    };
}

/**
 * Word tokenization for the dictionary hover feature
 *
 * Uses Intl.Segmenter when available (modern browsers) for accurate
 * locale-aware word boundary detection. Falls back to regex-based
 * splitting for older browsers.
 */

import type { Token } from "./types";

// Re-export Token type for convenience
export type { Token };

/**
 * Check if Intl.Segmenter is available in this environment
 */
function hasIntlSegmenter(): boolean {
    return (
        typeof Intl !== "undefined" &&
        typeof (Intl as typeof Intl & { Segmenter?: unknown }).Segmenter ===
            "function"
    );
}

/**
 * Tokenize text using Intl.Segmenter
 */
function tokenizeWithSegmenter(text: string, locale: string): Token[] {
    const Segmenter = (Intl as typeof Intl & { Segmenter: typeof Intl.Segmenter })
        .Segmenter;

    let segmenter: Intl.Segmenter;
    try {
        segmenter = new Segmenter(locale, { granularity: "word" });
    } catch {
        // Locale not supported, use English
        segmenter = new Segmenter("en", { granularity: "word" });
    }

    const segments = segmenter.segment(text);
    const tokens: Token[] = [];

    for (const segment of segments) {
        tokens.push({
            text: segment.segment,
            isWord: segment.isWordLike ?? false,
            normalized: segment.segment.toLowerCase().trim(),
            start: segment.index,
            end: segment.index + segment.segment.length,
        });
    }

    return tokens;
}

/**
 * Tokenize text using regex fallback
 * Splits on word boundaries, keeping punctuation and whitespace as separate tokens
 */
function tokenizeWithRegex(text: string): Token[] {
    const tokens: Token[] = [];
    // Match: words, whitespace sequences, or punctuation
    const pattern = /(\w+|[^\w\s]+|\s+)/g;
    let match: RegExpExecArray | null;

    while ((match = pattern.exec(text)) !== null) {
        const tokenText = match[0];
        const isWord = /^\w+$/.test(tokenText);

        tokens.push({
            text: tokenText,
            isWord,
            normalized: tokenText.toLowerCase().trim(),
            start: match.index,
            end: match.index + tokenText.length,
        });
    }

    return tokens;
}

/**
 * Tokenize text into words and non-word tokens
 *
 * @param text - The text to tokenize
 * @param locale - The locale for word boundary detection (e.g., "en", "en-US")
 * @returns Array of tokens with position information
 *
 * @example
 * ```ts
 * const tokens = tokenizeText("Hello, world!", "en");
 * // Returns tokens for: "Hello", ",", " ", "world", "!"
 * // Each token has: text, isWord, normalized, start, end
 * ```
 */
export function tokenizeText(text: string, locale: string): Token[] {
    if (!text) {
        return [];
    }

    if (hasIntlSegmenter()) {
        return tokenizeWithSegmenter(text, locale);
    }

    return tokenizeWithRegex(text);
}

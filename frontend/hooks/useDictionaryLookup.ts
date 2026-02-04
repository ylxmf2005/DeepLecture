"use client";

/**
 * React hook for dictionary lookups with debouncing
 */

import { useState, useEffect, useRef, useCallback } from "react";
import {
    createDictionaryLookup,
    type DictionaryEntry,
    type DictionaryProvider,
} from "@/lib/dictionary/lookup";

// Singleton provider instance
let provider: DictionaryProvider | null = null;

function getProvider(): DictionaryProvider {
    if (!provider) {
        provider = createDictionaryLookup();
    }
    return provider;
}

interface UseDictionaryLookupOptions {
    /** Debounce delay in ms (default: 300) */
    debounceMs?: number;
}

interface UseDictionaryLookupResult {
    /** Current lookup result (null if not found or not searched) */
    entry: DictionaryEntry | null;
    /** Whether a lookup is in progress */
    loading: boolean;
    /** Error message if lookup failed */
    error: string | null;
    /** Trigger a lookup for a word */
    lookup: (word: string, locale: string) => void;
    /** Clear the current result */
    clear: () => void;
    /** Check if a locale is supported */
    supports: (locale: string) => boolean;
}

/**
 * Hook for dictionary lookups with debouncing
 *
 * @example
 * ```tsx
 * const { entry, loading, lookup, clear } = useDictionaryLookup();
 *
 * const handleHover = (word: string) => {
 *   lookup(word, "en");
 * };
 *
 * const handleMouseLeave = () => {
 *   clear();
 * };
 * ```
 */
export function useDictionaryLookup(
    options: UseDictionaryLookupOptions = {}
): UseDictionaryLookupResult {
    const { debounceMs = 300 } = options;

    const [entry, setEntry] = useState<DictionaryEntry | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const abortControllerRef = useRef<AbortController | null>(null);
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const providerRef = useRef<DictionaryProvider>(getProvider());

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
        };
    }, []);

    const lookup = useCallback(
        (word: string, locale: string) => {
            // Clear any pending timeout
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }

            // Abort any in-flight request
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }

            // Check if locale is supported
            if (!providerRef.current.supports(locale)) {
                setEntry(null);
                setError(null);
                setLoading(false);
                return;
            }

            // Start debounce
            setLoading(true);
            setError(null);

            timeoutRef.current = setTimeout(async () => {
                const controller = new AbortController();
                abortControllerRef.current = controller;

                try {
                    const result = await providerRef.current.lookup(
                        word,
                        locale,
                        controller.signal
                    );

                    // Only update state if this request wasn't aborted
                    if (!controller.signal.aborted) {
                        setEntry(result);
                        setLoading(false);
                        if (!result) {
                            setError("Word not found");
                        }
                    }
                } catch (err) {
                    if (!controller.signal.aborted) {
                        setError("Lookup failed");
                        setEntry(null);
                        setLoading(false);
                    }
                }
            }, debounceMs);
        },
        [debounceMs]
    );

    const clear = useCallback(() => {
        // Clear timeout
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
            timeoutRef.current = null;
        }

        // Abort request
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }

        setEntry(null);
        setError(null);
        setLoading(false);
    }, []);

    const supports = useCallback((locale: string) => {
        return providerRef.current.supports(locale);
    }, []);

    return {
        entry,
        loading,
        error,
        lookup,
        clear,
        supports,
    };
}

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
    createDictionaryLookup,
    type DictionaryProvider,
    type DictionaryEntry,
} from "@/lib/dictionary/lookup";

// Mock fetch globally
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// Sample API response structure
const createMockApiResponse = (word: string): DictionaryEntry => ({
    word,
    phonetic: `/ˈ${word}/`,
    definitions: [
        {
            partOfSpeech: "noun",
            meaning: `Definition of ${word}`,
            example: `This is an example of ${word}.`,
        },
    ],
    examples: [`Example sentence with ${word}`],
    source: "api",
});

describe("createDictionaryLookup", () => {
    let provider: DictionaryProvider;

    beforeEach(() => {
        mockFetch.mockReset();
        provider = createDictionaryLookup();
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    describe("supports()", () => {
        it("returns true for English", () => {
            expect(provider.supports("en")).toBe(true);
            expect(provider.supports("en-US")).toBe(true);
            expect(provider.supports("en-GB")).toBe(true);
        });

        it("returns false for unsupported languages", () => {
            expect(provider.supports("zh")).toBe(false);
            expect(provider.supports("ja")).toBe(false);
            expect(provider.supports("ko")).toBe(false);
            expect(provider.supports("ar")).toBe(false);
        });
    });

    describe("lookup()", () => {
        it("fetches word definition from API", async () => {
            const mockResponse = [
                {
                    word: "apple",
                    phonetic: "/ˈæp.əl/",
                    meanings: [
                        {
                            partOfSpeech: "noun",
                            definitions: [
                                {
                                    definition: "A round fruit",
                                    example: "I ate an apple.",
                                },
                            ],
                        },
                    ],
                },
            ];

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(mockResponse),
            });

            const result = await provider.lookup("apple", "en");

            expect(result).not.toBeNull();
            expect(result?.word).toBe("apple");
            expect(result?.phonetic).toBe("/ˈæp.əl/");
            expect(result?.definitions).toHaveLength(1);
            expect(result?.definitions[0].meaning).toBe("A round fruit");
        });

        it("returns null for unsupported language", async () => {
            const result = await provider.lookup("苹果", "zh");

            expect(result).toBeNull();
            expect(mockFetch).not.toHaveBeenCalled();
        });

        it("returns null when API returns error", async () => {
            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 404,
            });

            const result = await provider.lookup("nonexistentword", "en");

            expect(result).toBeNull();
        });

        it("returns null when fetch throws", async () => {
            mockFetch.mockRejectedValueOnce(new Error("Network error"));

            const result = await provider.lookup("test", "en");

            expect(result).toBeNull();
        });
    });

    describe("caching", () => {
        it("caches successful lookups", async () => {
            const mockResponse = [
                {
                    word: "test",
                    phonetic: "/test/",
                    meanings: [
                        {
                            partOfSpeech: "noun",
                            definitions: [{ definition: "A test", example: "" }],
                        },
                    ],
                },
            ];

            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(mockResponse),
            });

            // First lookup
            await provider.lookup("test", "en");

            // Second lookup - should use cache
            await provider.lookup("test", "en");

            // Fetch should only be called once
            expect(mockFetch).toHaveBeenCalledTimes(1);
        });

        it("does not cache failed lookups", async () => {
            // First attempt fails
            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 404,
            });

            await provider.lookup("rare", "en");

            // Second attempt succeeds
            const mockResponse = [
                {
                    word: "rare",
                    phonetic: "/reər/",
                    meanings: [
                        {
                            partOfSpeech: "adjective",
                            definitions: [{ definition: "Not common" }],
                        },
                    ],
                },
            ];

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(mockResponse),
            });

            const result = await provider.lookup("rare", "en");

            // Should have called fetch twice (not cached the failure)
            expect(mockFetch).toHaveBeenCalledTimes(2);
            expect(result).not.toBeNull();
        });

        it("treats different words as different cache keys", async () => {
            const createResponse = (word: string) => [
                {
                    word,
                    meanings: [
                        {
                            partOfSpeech: "noun",
                            definitions: [{ definition: `${word} def` }],
                        },
                    ],
                },
            ];

            mockFetch
                .mockResolvedValueOnce({
                    ok: true,
                    json: () => Promise.resolve(createResponse("word1")),
                })
                .mockResolvedValueOnce({
                    ok: true,
                    json: () => Promise.resolve(createResponse("word2")),
                });

            await provider.lookup("word1", "en");
            await provider.lookup("word2", "en");

            expect(mockFetch).toHaveBeenCalledTimes(2);
        });
    });

    describe("abort signal", () => {
        it("respects abort signal", async () => {
            const controller = new AbortController();

            mockFetch.mockImplementation(
                () =>
                    new Promise((_, reject) => {
                        controller.signal.addEventListener("abort", () => {
                            reject(new DOMException("Aborted", "AbortError"));
                        });
                    })
            );

            // Use a unique word that won't be cached from previous tests
            const promise = provider.lookup("abortableword", "en", controller.signal);
            controller.abort();

            const result = await promise;
            expect(result).toBeNull();
        });
    });

    describe("audio URL extraction", () => {
        it("extracts audio URL from phonetics array", async () => {
            const mockResponse = [
                {
                    word: "example",
                    phonetic: "/ɪɡˈzæmpəl/",
                    phonetics: [
                        { text: "/ɪɡˈzæmpəl/", audio: "" },
                        {
                            text: "/ɪɡˈzæmpəl/",
                            audio: "https://api.dictionaryapi.dev/media/pronunciations/en/example-us.mp3",
                        },
                    ],
                    meanings: [
                        {
                            partOfSpeech: "noun",
                            definitions: [{ definition: "Something to be imitated" }],
                        },
                    ],
                },
            ];

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(mockResponse),
            });

            const result = await provider.lookup("example", "en");

            expect(result).not.toBeNull();
            expect(result?.audioUrl).toBe(
                "https://api.dictionaryapi.dev/media/pronunciations/en/example-us.mp3"
            );
        });

        it("returns undefined audioUrl when no audio in phonetics", async () => {
            const mockResponse = [
                {
                    word: "rare",
                    phonetic: "/reər/",
                    phonetics: [{ text: "/reər/", audio: "" }],
                    meanings: [
                        {
                            partOfSpeech: "adjective",
                            definitions: [{ definition: "Not common" }],
                        },
                    ],
                },
            ];

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(mockResponse),
            });

            const result = await provider.lookup("rare", "en");

            expect(result).not.toBeNull();
            expect(result?.audioUrl).toBeUndefined();
        });

        it("returns undefined audioUrl when phonetics array is missing", async () => {
            const mockResponse = [
                {
                    word: "test",
                    meanings: [
                        {
                            partOfSpeech: "noun",
                            definitions: [{ definition: "A test" }],
                        },
                    ],
                },
            ];

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(mockResponse),
            });

            const result = await provider.lookup("test", "en");

            expect(result).not.toBeNull();
            expect(result?.audioUrl).toBeUndefined();
        });

        it("ignores non-HTTP audio URLs", async () => {
            const mockResponse = [
                {
                    word: "invalid",
                    phonetics: [{ text: "/ɪnˈvælɪd/", audio: "relative/path.mp3" }],
                    meanings: [
                        {
                            partOfSpeech: "adjective",
                            definitions: [{ definition: "Not valid" }],
                        },
                    ],
                },
            ];

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(mockResponse),
            });

            const result = await provider.lookup("invalid", "en");

            expect(result).not.toBeNull();
            expect(result?.audioUrl).toBeUndefined();
        });
    });

    describe("word normalization", () => {
        it("normalizes word to lowercase before lookup", async () => {
            const mockResponse = [
                {
                    word: "hello",
                    meanings: [
                        {
                            partOfSpeech: "interjection",
                            definitions: [{ definition: "A greeting" }],
                        },
                    ],
                },
            ];

            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(mockResponse),
            });

            await provider.lookup("HELLO", "en");
            await provider.lookup("Hello", "en");
            await provider.lookup("hello", "en");

            // All three should hit cache after first fetch
            expect(mockFetch).toHaveBeenCalledTimes(1);
        });
    });
});

import { describe, it, expect, vi, beforeEach } from "vitest";
import { tokenizeText, type Token } from "@/lib/dictionary/tokenize";

describe("tokenizeText", () => {
    describe("basic English tokenization", () => {
        it("splits text on whitespace", () => {
            const tokens = tokenizeText("Hello world", "en");

            const words = tokens.filter((t) => t.isWord);
            expect(words).toHaveLength(2);
            expect(words[0].text).toBe("Hello");
            expect(words[1].text).toBe("world");
        });

        it("preserves whitespace tokens", () => {
            const tokens = tokenizeText("Hello world", "en");

            const whitespace = tokens.filter((t) => !t.isWord && t.text === " ");
            expect(whitespace.length).toBeGreaterThanOrEqual(1);
        });

        it("handles punctuation at end of words", () => {
            const tokens = tokenizeText("Hello, world!", "en");

            const words = tokens.filter((t) => t.isWord);
            expect(words).toHaveLength(2);
            expect(words[0].text).toBe("Hello");
            expect(words[1].text).toBe("world");
        });

        it("separates punctuation as non-word tokens", () => {
            const tokens = tokenizeText("Hello, world!", "en");

            const punctuation = tokens.filter(
                (t) => !t.isWord && (t.text === "," || t.text === "!")
            );
            expect(punctuation.length).toBeGreaterThanOrEqual(2);
        });

        it("normalizes words to lowercase", () => {
            const tokens = tokenizeText("HELLO World", "en");

            const words = tokens.filter((t) => t.isWord);
            expect(words[0].normalized).toBe("hello");
            expect(words[1].normalized).toBe("world");
        });
    });

    describe("position tracking", () => {
        it("tracks start and end positions for each token", () => {
            const tokens = tokenizeText("Hi there", "en");

            // "Hi" should start at 0
            const hi = tokens.find((t) => t.text === "Hi");
            expect(hi?.start).toBe(0);
            expect(hi?.end).toBe(2);

            // "there" should start at 3 (after "Hi ")
            const there = tokens.find((t) => t.text === "there");
            expect(there?.start).toBe(3);
            expect(there?.end).toBe(8);
        });

        it("consecutive positions cover entire string", () => {
            const text = "A B C";
            const tokens = tokenizeText(text, "en");

            // Verify tokens cover the entire string
            const reconstructed = tokens.map((t) => t.text).join("");
            expect(reconstructed).toBe(text);
        });
    });

    describe("edge cases", () => {
        it("handles empty string", () => {
            const tokens = tokenizeText("", "en");
            expect(tokens).toHaveLength(0);
        });

        it("handles string with only whitespace", () => {
            const tokens = tokenizeText("   ", "en");

            const words = tokens.filter((t) => t.isWord);
            expect(words).toHaveLength(0);
        });

        it("handles string with only punctuation", () => {
            const tokens = tokenizeText("...", "en");

            const words = tokens.filter((t) => t.isWord);
            expect(words).toHaveLength(0);
        });

        it("handles contractions", () => {
            const tokens = tokenizeText("don't won't", "en");

            // Contractions may be split or kept together depending on implementation
            // Just verify we get reasonable word tokens
            const words = tokens.filter((t) => t.isWord);
            expect(words.length).toBeGreaterThanOrEqual(2);
        });

        it("handles numbers mixed with text", () => {
            const tokens = tokenizeText("Chapter 1 begins", "en");

            const words = tokens.filter((t) => t.isWord);
            // "Chapter", "1", "begins" could all be words depending on impl
            expect(words.length).toBeGreaterThanOrEqual(2);
        });
    });

    describe("fallback behavior", () => {
        it("works without Intl.Segmenter (regex fallback)", () => {
            // Force fallback by using unsupported locale
            const tokens = tokenizeText("Test sentence", "xx-invalid");

            const words = tokens.filter((t) => t.isWord);
            expect(words.length).toBeGreaterThanOrEqual(2);
        });
    });

    describe("locale awareness", () => {
        it("accepts different locale codes", () => {
            // Should not throw for different locales
            expect(() => tokenizeText("test", "en")).not.toThrow();
            expect(() => tokenizeText("test", "en-US")).not.toThrow();
            expect(() => tokenizeText("test", "de")).not.toThrow();
        });
    });
});

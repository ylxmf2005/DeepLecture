import { describe, expect, it } from "vitest";
import {
    isAutoSourceLanguage,
    isUnresolvedAutoSourceLanguage,
    resolveConfiguredSourceLanguage,
} from "@/lib/sourceLanguage";

describe("sourceLanguage helpers", () => {
    it("resolves explicit source language unchanged", () => {
        expect(resolveConfiguredSourceLanguage("ja", null)).toBe("ja");
    });

    it("resolves auto source language from detected language", () => {
        expect(resolveConfiguredSourceLanguage("auto", "ja")).toBe("ja");
    });

    it("reports unresolved auto source language", () => {
        expect(isUnresolvedAutoSourceLanguage("auto", null)).toBe(true);
    });

    it("detects the auto sentinel", () => {
        expect(isAutoSourceLanguage("auto")).toBe(true);
        expect(isAutoSourceLanguage("en")).toBe(false);
    });
});

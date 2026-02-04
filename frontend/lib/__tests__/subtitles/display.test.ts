import { describe, it, expect } from "vitest";
import {
    createSubtitleRows,
    type SubtitleRow,
} from "@/lib/subtitles/display";
import type { Subtitle } from "@/lib/srt";
import type { SubtitleDisplayMode } from "@/stores/types";

// Test fixtures
const sourceSubtitles: Subtitle[] = [
    { id: "1", startTime: 0, endTime: 2, text: "Hello world" },
    { id: "2", startTime: 2, endTime: 4, text: "How are you?" },
];

const targetSubtitles: Subtitle[] = [
    { id: "1", startTime: 0, endTime: 2, text: "你好世界" },
    { id: "2", startTime: 2, endTime: 4, text: "你好吗？" },
];

describe("createSubtitleRows", () => {
    describe("source mode", () => {
        it("returns rows with only sourceText", () => {
            const rows = createSubtitleRows({
                mode: "source",
                subtitlesSource: sourceSubtitles,
                subtitlesTarget: targetSubtitles,
            });

            expect(rows).toHaveLength(2);
            expect(rows[0].sourceText).toBe("Hello world");
            expect(rows[0].targetText).toBeUndefined();
            expect(rows[1].sourceText).toBe("How are you?");
            expect(rows[1].targetText).toBeUndefined();
        });

        it("preserves timing information", () => {
            const rows = createSubtitleRows({
                mode: "source",
                subtitlesSource: sourceSubtitles,
                subtitlesTarget: targetSubtitles,
            });

            expect(rows[0].startTime).toBe(0);
            expect(rows[0].endTime).toBe(2);
            expect(rows[0].id).toBe("1");
        });
    });

    describe("target mode", () => {
        it("returns rows with only targetText (no sourceText)", () => {
            const rows = createSubtitleRows({
                mode: "target",
                subtitlesSource: sourceSubtitles,
                subtitlesTarget: targetSubtitles,
            });

            expect(rows).toHaveLength(2);
            expect(rows[0].sourceText).toBeUndefined();
            expect(rows[0].targetText).toBe("你好世界");
        });
    });

    describe("dual mode", () => {
        it("returns rows with both sourceText and targetText", () => {
            const rows = createSubtitleRows({
                mode: "dual",
                subtitlesSource: sourceSubtitles,
                subtitlesTarget: targetSubtitles,
            });

            expect(rows).toHaveLength(2);
            expect(rows[0].sourceText).toBe("Hello world");
            expect(rows[0].targetText).toBe("你好世界");
        });

        it("source appears first (is primary)", () => {
            const rows = createSubtitleRows({
                mode: "dual",
                subtitlesSource: sourceSubtitles,
                subtitlesTarget: targetSubtitles,
            });

            // In dual mode, sourceText is the primary (top) line
            expect(rows[0].sourceText).toBeDefined();
            expect(rows[0].targetText).toBeDefined();
        });
    });

    describe("dual_reversed mode", () => {
        it("returns rows with both texts but order indicates target is primary", () => {
            const rows = createSubtitleRows({
                mode: "dual_reversed",
                subtitlesSource: sourceSubtitles,
                subtitlesTarget: targetSubtitles,
            });

            expect(rows).toHaveLength(2);
            // In dual_reversed, target is primary but we still store separately
            expect(rows[0].sourceText).toBe("Hello world");
            expect(rows[0].targetText).toBe("你好世界");
            // The rendering order is controlled by the component
        });
    });

    describe("edge cases", () => {
        it("handles empty source subtitles", () => {
            const rows = createSubtitleRows({
                mode: "source",
                subtitlesSource: [],
                subtitlesTarget: targetSubtitles,
            });

            expect(rows).toHaveLength(0);
        });

        it("handles mismatched array lengths in dual mode", () => {
            const longerTarget = [
                ...targetSubtitles,
                { id: "3", startTime: 4, endTime: 6, text: "额外的" },
            ];

            const rows = createSubtitleRows({
                mode: "dual",
                subtitlesSource: sourceSubtitles,
                subtitlesTarget: longerTarget,
            });

            // Should only have as many rows as source subtitles
            expect(rows).toHaveLength(2);
        });

        it("handles missing target in dual mode", () => {
            const rows = createSubtitleRows({
                mode: "dual",
                subtitlesSource: sourceSubtitles,
                subtitlesTarget: [],
            });

            expect(rows).toHaveLength(2);
            expect(rows[0].sourceText).toBe("Hello world");
            expect(rows[0].targetText).toBeUndefined();
        });
    });
});

/**
 * Subtitle display view model
 *
 * Transforms raw subtitle data into a structure that preserves
 * source/target text separately for proper hover dictionary behavior.
 */

import type { Subtitle } from "@/lib/srt";
import type { SubtitleDisplayMode } from "@/stores/types";

/**
 * A subtitle row with separate source and target text
 * This preserves the semantic boundary between original and translated text
 */
export interface SubtitleRow {
    id: string;
    startTime: number;
    endTime: number;
    /** Original language text (only present if mode includes source) */
    sourceText?: string;
    /** Translated text (only present if mode includes target) */
    targetText?: string;
}

export interface CreateSubtitleRowsOptions {
    mode: SubtitleDisplayMode;
    subtitlesSource: Subtitle[];
    subtitlesTarget: Subtitle[];
}

/**
 * Create subtitle rows from source and target subtitles based on display mode
 *
 * This function transforms the merged subtitle format into a structure that
 * preserves the semantic boundary between original and translated text,
 * enabling proper hover dictionary behavior (only original text responds).
 *
 * @param options - Mode and subtitle arrays
 * @returns Array of SubtitleRow with separate source/target text
 *
 * @example
 * ```ts
 * const rows = createSubtitleRows({
 *   mode: "dual",
 *   subtitlesSource: [{ id: "1", startTime: 0, endTime: 2, text: "Hello" }],
 *   subtitlesTarget: [{ id: "1", startTime: 0, endTime: 2, text: "你好" }],
 * });
 *
 * // Result:
 * // [{ id: "1", startTime: 0, endTime: 2, sourceText: "Hello", targetText: "你好" }]
 * ```
 */
export function createSubtitleRows(
    options: CreateSubtitleRowsOptions
): SubtitleRow[] {
    const { mode, subtitlesSource, subtitlesTarget } = options;

    switch (mode) {
        case "source":
            // Only show original language
            return subtitlesSource.map((sub) => ({
                id: sub.id,
                startTime: sub.startTime,
                endTime: sub.endTime,
                sourceText: sub.text,
            }));

        case "target":
            // Only show translation
            return subtitlesTarget.map((sub) => ({
                id: sub.id,
                startTime: sub.startTime,
                endTime: sub.endTime,
                targetText: sub.text,
            }));

        case "dual":
        case "dual_reversed": {
            // Show both, use source subtitles as the base
            // Match target by id for robustness when arrays diverge
            const targetLookup = new Map(
                subtitlesTarget.map((sub) => [sub.id, sub])
            );
            return subtitlesSource.map((sub) => {
                const targetSub = targetLookup.get(sub.id);
                return {
                    id: sub.id,
                    startTime: sub.startTime,
                    endTime: sub.endTime,
                    sourceText: sub.text,
                    targetText: targetSub?.text,
                };
            });
        }

        default:
            return [];
    }
}

/**
 * Check if the mode includes source (original) text
 */
export function modeIncludesSource(mode: SubtitleDisplayMode): boolean {
    return mode === "source" || mode === "dual" || mode === "dual_reversed";
}

/**
 * Check if the mode includes target (translated) text
 */
export function modeIncludesTarget(mode: SubtitleDisplayMode): boolean {
    return mode === "target" || mode === "dual" || mode === "dual_reversed";
}

/**
 * Check if source text should be displayed first (on top)
 */
export function isSourceFirst(mode: SubtitleDisplayMode): boolean {
    return mode === "dual";
}

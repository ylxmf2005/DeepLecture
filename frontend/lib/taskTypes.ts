/**
 * Shared task type normalization and mapping.
 *
 * Single source of truth for task type aliases, content refresh sets,
 * and processing action mappings. Used by hooks and tested independently.
 */

export type ProcessingAction = "generate" | "translate" | "video" | "timeline" | null;

/** Legacy task type aliases → canonical names. */
const LEGACY_ALIASES: Record<string, string> = {
    subtitle_enhancement: "subtitle_translation",
};

/** Normalize a raw task type string to its canonical form. */
export function normalizeTaskType(raw: string): string {
    return LEGACY_ALIASES[raw] ?? raw;
}

/** Task types that trigger a content metadata refresh on completion. */
const CONTENT_REFRESH_TASK_TYPES = new Set([
    "subtitle_generation",
    "subtitle_translation",
    "timeline_generation",
    "video_generation",
    "video_merge",
    "video_import_url",
    "pdf_merge",
]);

/** Check if a task type triggers content refresh. Normalizes legacy types. */
export function isContentRefreshTask(type: string): boolean {
    return CONTENT_REFRESH_TASK_TYPES.has(normalizeTaskType(type));
}

/** Mapping of canonical task type → processing action for UI state. */
const TASK_TO_ACTION: Record<string, ProcessingAction> = {
    subtitle_generation: "generate",
    subtitle_translation: "translate",
    timeline_generation: "timeline",
    video_generation: "video",
    video_merge: "video",
    video_import_url: "video",
};

/** Get the processing action for a task type, or null if not a processing task. */
export function taskToProcessingAction(type: string): ProcessingAction {
    return TASK_TO_ACTION[normalizeTaskType(type)] ?? null;
}

/** Notification labels for all 13 backend task types. */
export const TASK_LABELS: Record<string, { success: string; error: string }> = {
    subtitle_generation: {
        success: "Subtitles generated successfully",
        error: "Subtitle generation failed",
    },
    subtitle_translation: {
        success: "Translation completed",
        error: "Translation failed",
    },
    timeline_generation: {
        success: "Timeline generated successfully",
        error: "Timeline generation failed",
    },
    video_generation: {
        success: "Video generated successfully",
        error: "Video generation failed",
    },
    video_merge: {
        success: "Videos merged successfully",
        error: "Video merge failed",
    },
    video_import_url: {
        success: "Video imported successfully",
        error: "Video import failed",
    },
    pdf_merge: {
        success: "PDFs merged successfully",
        error: "PDF merge failed",
    },
    voiceover_generation: {
        success: "Voiceover generated successfully",
        error: "Voiceover generation failed",
    },
    slide_explanation: {
        success: "Slide explanation ready",
        error: "Slide explanation failed",
    },
    fact_verification: {
        success: "Fact verification complete",
        error: "Fact verification failed",
    },
    cheatsheet_generation: {
        success: "Cheatsheet generated successfully",
        error: "Cheatsheet generation failed",
    },
    note_generation: {
        success: "Notes generated successfully",
        error: "Note generation failed",
    },
    quiz_generation: {
        success: "Quiz generated successfully",
        error: "Quiz generation failed",
    },
};

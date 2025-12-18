/**
 * API Module - Unified API interface re-exports
 *
 * All API functions use camelCase internally.
 * Axios interceptors handle snake_case ↔ camelCase conversion automatically.
 */

export { api, API_BASE_URL, createCancelToken, isCancel, createAbortController, withAbortSignal } from "./client";

export * from "./types";

// Error handling
export { APIError, wrapAPIError, isAPIError } from "./errors";
export type { APIErrorCode, APIErrorContext } from "./errors";

// Content APIs
export {
    uploadContent,
    uploadNoteImage,
    importVideoFromUrl,
    renameContent,
    generateSlideLecture,
    getContentMetadata,
    listContent,
    deleteContent,
} from "./content";

// Subtitle APIs
export {
    generateSubtitles,
    enhanceAndTranslate,
    getSubtitles,
    getSubtitlesVtt,
} from "./subtitle";

// Voiceover APIs
export {
    generateVoiceover,
    listVoiceovers,
    deleteVoiceover,
    getVoiceoverSyncTimeline,
    updateVoiceover,
} from "./voiceover";

// Timeline APIs
export { getTimeline, generateTimeline } from "./timeline";
export type { GetTimelineOptions, GenerateTimelineOptions } from "./timeline";

// Notes APIs
export { getVideoNote, saveVideoNote, generateVideoNote } from "./notes";
export type { GenerateVideoNoteParams } from "./notes";

// Explanation APIs
export { captureSlide, explainSlide, getExplanationHistory, deleteExplanation } from "./explanation";
export type { ExplainSlideParams } from "./explanation";

// Ask APIs
export {
    listAskConversations,
    createAskConversation,
    getAskConversation,
    deleteAskConversation,
    askVideoQuestion,
    summarizeContext,
} from "./ask";
export type { AskVideoQuestionParams, SummarizeContextParams } from "./ask";

// Config APIs
export { getLanguageSettings, getLive2DModels, getNoteDefaults, getAppConfig } from "./config";

// Task APIs
export { getTaskStatus, getTasksForContent, createTaskEventSource, getJobStatus } from "./task";

// Fact Verification APIs
export { getFactVerificationReport, generateFactVerification } from "./factVerification";
export type { GenerateFactVerificationParams, GenerateFactVerificationResponse } from "./factVerification";

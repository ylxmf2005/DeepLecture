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

// Cheatsheet APIs
export { getVideoCheatsheet, saveVideoCheatsheet, generateVideoCheatsheet } from "./cheatsheet";
export type { GenerateCheatsheetParams, CheatsheetContextMode, CheatsheetCriticality, CheatsheetSubjectType } from "./cheatsheet";

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
export { getGlobalConfig, putGlobalConfig, deleteGlobalConfig } from "./globalConfig";

// Task APIs
export { getTaskStatus, getTasksForContent, createTaskEventSource, getJobStatus } from "./task";

// Quiz APIs
export { getQuiz, generateQuiz } from "./quiz";
export type { QuizItem, QuizResponse, GenerateQuizResponse, GenerateQuizParams, QuizContextMode, QuizCriticality, QuizSubjectType } from "./quiz";

// Fact Verification APIs
export { getFactVerificationReport, generateFactVerification } from "./factVerification";
export type { GenerateFactVerificationParams, GenerateFactVerificationResponse } from "./factVerification";

// Bookmark APIs
export { listBookmarks, createBookmark, updateBookmark, deleteBookmark } from "./bookmarks";
export type { BookmarkItem, BookmarkListResponse } from "./bookmarks";

/**
 * API Types - TypeScript interfaces for API responses
 *
 * NAMING CONVENTION:
 * - All fields use camelCase (UI standard)
 * - Axios interceptors handle snake_case ↔ camelCase conversion
 * - Wire format is snake_case (see reports/api-contract-v1.md)
 */

import type { AskContextItem, AskMessage } from "@/lib/askTypes";

// =============================================================================
// COMMON TYPES
// =============================================================================

export type FeatureStatus = "none" | "pending" | "processing" | "ready" | "error";
export type TaskStatus = "pending" | "processing" | "ready" | "error";
export type ContentType = "video" | "slide";

// =============================================================================
// CONTENT TYPES
// =============================================================================

export interface ContentItem {
    id: string;
    type: ContentType;
    filename: string;
    createdAt: string;
    videoStatus?: FeatureStatus;
    subtitleStatus?: FeatureStatus;
    translationStatus?: FeatureStatus;
    enhancedStatus?: FeatureStatus;
    timelineStatus?: FeatureStatus;
    notesStatus?: FeatureStatus;
    pageCount?: number;
    sourceType?: string;
    sourceUrl?: string;
}

export interface ContentListResponse {
    content: ContentItem[];
    count: number;
}

export interface UploadResponse {
    contentId: string;
    filename: string;
    contentType: ContentType;
    message: string;
}

export interface ImportResponse {
    contentId: string;
    filename: string;
    message: string;
    status?: TaskStatus;
    taskId?: string;
}

export interface RenameResponse {
    id: string;
    filename: string;
    message: string;
}

export interface DeleteContentResponse {
    deleted: boolean;
    message?: string;
}

// =============================================================================
// TASK TYPES
// =============================================================================

export interface TaskResult {
    kind: string;
    url?: string;
}

export interface TaskStatusResponse {
    id: string;
    type: string;
    contentId: string;
    status: TaskStatus;
    progress: number;
    error: string | null;
    result: TaskResult | null;
    metadata: Record<string, unknown>;
    createdAt: string;
    updatedAt: string;
}

export interface TaskListResponse {
    contentId: string;
    tasks: TaskStatusResponse[];
    count: number;
}

// =============================================================================
// SUBTITLE TYPES
// =============================================================================

export interface SubtitleSegment {
    start: number;
    end: number;
    text: string;
}

export interface SubtitleResponse {
    contentId: string;
    language: string;
    segments: SubtitleSegment[];
    count: number;
}

export interface SubtitleGenerateResponse {
    contentId: string;
    taskId?: string;
    message: string;
    status: TaskStatus;
}

export interface TranslationResponse {
    contentId: string;
    taskId?: string;
    message: string;
    status: TaskStatus;
}

export interface EnhancementResponse {
    contentId: string;
    taskId?: string;
    message: string;
    status: TaskStatus;
}

export type SubtitleSource = "original" | "translated";

// =============================================================================
// TIMELINE TYPES
// =============================================================================

export interface TimelineEntry {
    id: number;
    kind: string;
    start: number;
    end: number;
    title: string;
    markdown: string;
}

export interface TimelineResponse {
    contentId: string;
    language: string;
    entries: TimelineEntry[];
    count: number;
    cached: boolean;
    status: FeatureStatus;
}

export interface TimelineGenerateResponse {
    contentId: string;
    taskId: string;
    status: "pending";
    message: string;
}

// =============================================================================
// VOICEOVER TYPES
// =============================================================================

export interface VoiceoverEntry {
    id: string;
    name: string;
    language: string;
    subtitleSource: SubtitleSource | "path";
    createdAt: string;
    status?: "processing" | "done" | "error";
    error?: string | null;
    updatedAt?: string;
    duration?: number;
}

export interface VoiceoverResponse {
    voiceover: VoiceoverEntry;
    message: string;
    taskId?: string;
}

export interface ListVoiceoversResponse {
    voiceovers: VoiceoverEntry[];
}

export interface SyncTimelineSegment {
    dstStart: number;
    dstEnd: number;
    srcStart: number;
    srcEnd: number;
    speed: number;
}

export interface SyncTimeline {
    version: number;
    sourceVideoDuration: number;
    voiceoverAudioDuration: number;
    segments: SyncTimelineSegment[];
}

// =============================================================================
// NOTES TYPES
// =============================================================================

export interface VideoNoteResponse {
    contentId: string;
    content: string;
    updatedAt: string | null;
}

export type NoteContextMode = "subtitle" | "slide" | "both";

export interface GenerateVideoNoteOutlinePart {
    id: number;
    title: string;
}

export interface GenerateVideoNoteResponse {
    contentId: string;
    taskId: string;
    status: TaskStatus;
    message: string;
}

// =============================================================================
// EXPLANATION TYPES
// =============================================================================

export interface CaptureResponse {
    imageUrl: string;
    timestamp: number;
    /** @deprecated Will be removed - use imageUrl instead */
    imagePath?: string;
}

export interface ExplanationData {
    id?: string;
    timestamp: number;
    explanation: string | null;  // null when pending
    createdAt: string;
    imageUrl?: string;
    language?: string;
    /** @deprecated Will be removed - use imageUrl instead */
    imagePath?: string;
}

export interface ExplanationResponse {
    explanation: string;
    data: ExplanationData;
}

export interface ExplanationHistoryResponse {
    history: ExplanationData[];
}

export interface ExplanationGenerateResponse {
    contentId: string;
    taskId: string;
    entryId: string;
    status: "pending";
    message: string;
}

// =============================================================================
// ASK TYPES
// =============================================================================

export interface AskResponse {
    answer: string;
}

export interface AskConversationSummary {
    id: string;
    title: string;
    createdAt: string | null;
    updatedAt: string | null;
    lastMessagePreview?: string;
}

export interface AskConversation {
    id: string;
    title: string;
    createdAt: string | null;
    updatedAt: string | null;
    messages: AskMessage[];
}

export interface ListAskConversationsResponse {
    contentId: string;
    conversations: AskConversationSummary[];
}

export interface AskConversationResponse {
    contentId: string;
    conversation: AskConversation;
}

export interface SummarizeContextResponse {
    summary: string;
}

// =============================================================================
// CONFIG TYPES
// =============================================================================

export interface LanguageSettings {
    originalLanguage: string;
    translatedLanguage: string;
}

export interface Live2DModel {
    name: string;
    path: string;
}

export interface NoteDefaultsResponse {
    defaultContextMode: NoteContextMode;
}

// =============================================================================
// UNIFIED CONFIG TYPES (New Provider/Registry Architecture)
// =============================================================================

export interface ModelOption {
    id: string;
    name: string;
    provider: string;
}

export interface PromptOption {
    id: string;
    name: string;
    description: string | null;
    isDefault: boolean;
}

export interface PromptFunctionConfig {
    options: PromptOption[];
    defaultImplId: string;
}

export interface AppConfigResponse {
    llm: {
        models: ModelOption[];
        defaultModel: string;
    };
    tts: {
        models: ModelOption[];
        defaultModel: string;
    };
    prompts: Record<string, PromptFunctionConfig>;
}

// =============================================================================
// SLIDE TYPES
// =============================================================================

export interface SlideDeckUploadResponse {
    deckId: string;
    filename: string;
    pageCount: number;
    message: string;
}

export interface SlideLectureGenerationResponse {
    deckId: string;
    status: TaskStatus;
    message: string;
    taskId?: string;
}

export interface SlideDeckMeta {
    deckId: string;
    filename: string;
    pageCount: number;
    createdAt?: string | null;
    status?: string;
}

// =============================================================================
// MERGE TYPES
// =============================================================================

export interface VideoMergeResponse {
    contentId: string;
    filename: string;
    contentType: ContentType;
    message: string;
    status: TaskStatus;
    taskId?: string;
}

// =============================================================================
// RE-EXPORTS
// =============================================================================

export type { AskContextItem, AskMessage };

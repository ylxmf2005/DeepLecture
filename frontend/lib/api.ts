import axios from 'axios';
import type { AskContextItem, AskMessage } from "@/lib/askTypes";

// Feature status type
export type FeatureStatus = "none" | "processing" | "ready" | "error";

export interface ContentItem {
    type: "video" | "slide";
    id: string;
    filename: string;
    createdAt: string;
    // New feature status fields
    videoStatus?: FeatureStatus;
    subtitleStatus?: FeatureStatus;
    translationStatus?: FeatureStatus;
    enhancedStatus?: FeatureStatus;
    timelineStatus?: FeatureStatus;
    notesStatus?: FeatureStatus;
    // Other fields
    pageCount?: number;
    sourceType?: string;
    sourceUrl?: string;
}

export interface UploadResponse {
    videoId: string;
    filename: string;
    message: string;
}

export interface ImportResponse {
    contentId: string;
    filename: string;
    message: string;
    status?: "processing" | "ready";
    job_id?: string;
    task_id?: string;
}

export interface VideoMergeResponse {
    contentId: string;
    filename: string;
    contentType: string;
    message: string;
    status: "processing" | "ready";
    job_id?: string;
    task_id?: string;
}

export interface RenameResponse {
    id: string;
    filename: string;
    message: string;
}

export interface SubtitleResponse {
    subtitle_path: string;
    message: string;
    status?: "processing" | "ready";
    job_id?: string;
    task_id?: string;
}

export interface TranslationResponse {
    translated_path: string;
    message: string;
    status?: "processing" | "ready";
    job_id?: string;
    task_id?: string;
}

export interface VoiceoverResponse {
    voiceover: VoiceoverEntry;
    message: string;
    job_id?: string;
    task_id?: string;
}

export interface EnhancementResponse {
    enhanced_path: string;
    background_path: string;
    message: string;
    status?: "processing" | "ready";
    job_id?: string;
    task_id?: string;
}

export type SubtitleSource = "original" | "translated";

export interface VoiceoverEntry {
    id: string;
    name: string;
    language: string;
    subtitle_source: SubtitleSource | "path";
    subtitle_path: string;
    voiceover_audio_path: string;
    dubbed_video_path: string;
    created_at: string;
}

export interface ListVoiceoversResponse {
    voiceovers: VoiceoverEntry[];
}

export interface TimelineEntry {
    id: number;
    kind: string;
    start: number;
    end: number;
    title: string;
    markdown: string;
}

export interface TimelineResponse {
    video_id: string;
    language: string;
    generated_at: string;
    timeline: TimelineEntry[];
    count: number;
    cached: boolean;
    timeline_path?: string;
}

export interface LanguageSettings {
    original_language: string;
    ai_language: string;
    translated_language: string;
}

// Slide PDF & AI lecture video

export interface SlideDeckUploadResponse {
    deck_id: string;
    filename: string;
    page_count: number;
    message: string;
}

export interface SlideLectureGenerationResponse {
    deck_id: string;
    lecture_video_path: string;
    subtitle_path: string;
    status: "processing" | "ready";
    message: string;
    job_id?: string;
    task_id?: string;
}

export interface SlideDeckMeta {
    deck_id: string;
    filename: string;
    pdf_path?: string | null;
    output_dir?: string | null;
    page_count: number;
    created_at?: string | null;
    lecture_video_path?: string | null;
    subtitle_path?: string | null;
    status?: string;
}

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:11393';

export const api = axios.create({
    baseURL: `${API_BASE_URL}/api`,
});

// Response interceptor to handle unified response format
// Backend returns: {success: true, data: <actual_data>} or {success: false, error: <message>}
api.interceptors.response.use(
    (response) => {
        // Check if response has unified format
        if (response.data && typeof response.data === 'object' && 'success' in response.data) {
            if (response.data.success) {
                // Unwrap successful response
                response.data = response.data.data;
            } else {
                // Convert error response to exception
                const error = new Error(response.data.error || 'Request failed');
                throw error;
            }
        }
        // Return response for non-unified format (backward compatibility)
        return response;
    },
    (error) => {
        // Pass through network/HTTP errors
        return Promise.reject(error);
    }
);

export const uploadContent = async (file: File) => {
    const formData = new FormData();
    const isVideo = file.type.startsWith('video/');
    const isPdf = file.type === 'application/pdf';

    if (isVideo) {
        formData.append('video', file);
    } else if (isPdf) {
        formData.append('pdf', file);
    } else {
        throw new Error('Unsupported file type');
    }

    const response = await api.post<{
        contentId: string;
        filename: string;
        contentType: 'video' | 'slide';
        message: string;
    }>('/content/upload', formData);
    return response.data;
};

export const uploadNoteImage = async (videoId: string, imageBlob: Blob) => {
    const formData = new FormData();
    const timestamp = Date.now();
    const filename = `paste_${timestamp}.png`;
    formData.append('image', imageBlob, filename);
    formData.append('video_id', videoId);

    const response = await api.post<{
        filename: string;
        path: string;
        url: string;
    }>('/content/upload-note-image', formData);
    return response.data;
};

export const importVideoFromUrl = async (url: string, customName?: string) => {
    const response = await api.post<ImportResponse>('/content/import-url', {
        url,
        custom_name: customName,
    });
    return response.data;
};

export const renameContent = async (contentId: string, newName: string) => {
    const response = await api.post<RenameResponse>(`/content/${contentId}/rename`, {
        new_name: newName,
    });
    return response.data;
};

export const generateSlideLecture = async (contentId: string, force: boolean = false) => {
    const response = await api.post<SlideLectureGenerationResponse>(`/content/${contentId}/generate-video`, { force });
    return response.data;
};

export const getContentMetadata = async (contentId: string) => {
    const response = await api.get<ContentItem>(`/content/${contentId}`);
    return response.data;
};

export const listContent = async () => {
    const response = await api.get<{ content: ContentItem[]; count: number }>('/content/list');
    return response.data;
};

export const generateSubtitles = async (videoId: string, language: string = 'en', force: boolean = false) => {
    const response = await api.post<SubtitleResponse>(
        `/content/${videoId}/generate-subtitles`,
        {
            source_language: language,
            force,
        },
    );
    return response.data;
};

export const enhanceAndTranslate = async (contentId: string, targetLanguage: string) => {
    const response = await api.post<TranslationResponse>(`/content/${contentId}/translate-subtitles`, {
        target_language: targetLanguage,
    });
    return response.data;
};

export const generateVoiceover = async (
    videoId: string,
    subtitleSource: SubtitleSource,
    voiceoverName: string,
    language: string = "zh"
) => {
    const response = await api.post<VoiceoverResponse>(`/content/${videoId}/voiceovers`, {
        subtitle_source: subtitleSource,
        voiceover_name: voiceoverName,
        language,
    });
    return response.data;
};

export const listVoiceovers = async (videoId: string) => {
    const response = await api.get<ListVoiceoversResponse>(`/content/${videoId}/voiceovers`);
    return response.data;
};

export const generateTimeline = async (
    videoId: string,
    language: string = "zh",
    force: boolean = false,
    learnerProfile?: string
) => {
    const response = await api.post<TimelineResponse>(`/content/${videoId}/timelines`, {
        language,
        force,
        learner_profile: learnerProfile,
    });
    return response.data;
};

export const getLanguageSettings = async () => {
    const response = await api.get<LanguageSettings>("/config/languages");
    return response.data;
};

export interface CaptureResponse {
    image_url: string;
    image_path: string;
    timestamp: number;
}

export interface ExplanationResponse {
    explanation: string;
    data: ExplanationData;
}

export interface ExplanationData {
    id?: string;
    timestamp: number;
    image_path: string;
    explanation: string;
    created_at: string;
    image_url?: string;
}

export interface ExplanationHistoryResponse {
    history: ExplanationData[];
}

export const captureSlide = async (videoId: string, timestamp: number) => {
    const response = await api.post<CaptureResponse>('/capture-slide', {
        video_id: videoId,
        timestamp,
    });
    return response.data;
};

export const explainSlide = async (
    videoId: string,
    imagePath: string,
    timestamp: number,
    learnerProfile?: string,
    subtitleContextWindowSeconds?: number,
) => {
    const response = await api.post<ExplanationResponse>('/explain-slide', {
        video_id: videoId,
        image_path: imagePath,
        timestamp,
        learner_profile: learnerProfile,
        subtitle_context_window_seconds: subtitleContextWindowSeconds,
    });
    return response.data;
};

export const getExplanationHistory = async (videoId: string) => {
    const response = await api.get<ExplanationHistoryResponse>('/explanation-history', {
        params: { video_id: videoId },
    });
    return response.data;
};

export const deleteExplanation = async (videoId: string, id: string) => {
    await api.post('/delete-explanation', {
        video_id: videoId,
        id,
    });
};

export const getContentSubtitles = async (
    contentId: string,
    lang: "original" | "translated" | "enhanced" = "original",
    format: "srt" | "vtt" = "srt",
) => {
    const response = await api.get<string>(`/content/${contentId}/subtitles`, {
        params: { lang, format },
    });
    return response.data;
};

export interface VideoNoteResponse {
    video_id: string;
    content: string;
    updated_at: string | null;
}

export type NoteContextMode = "auto" | "subtitle" | "slide" | "both";

export interface GenerateVideoNoteOutlinePart {
    id: number;
    title: string;
}

export interface GenerateVideoNoteResponse {
    video_id: string;
    note_path: string;
    status: "processing" | "ready" | "error";
    message: string;
    job_id?: string;
}

export const getVideoNote = async (videoId: string) => {
    const response = await api.get<VideoNoteResponse>("/notes", {
        params: { video_id: videoId },
    });
    return response.data;
};

export const saveVideoNote = async (videoId: string, content: string) => {
    const response = await api.post<VideoNoteResponse>("/notes", {
        video_id: videoId,
        content,
    });
    return response.data;
};

export const generateVideoNote = async (params: {
    videoId: string;
    contextMode?: NoteContextMode;
    instruction?: string;
    learnerProfile?: string;
    maxParts?: number;
}) => {
    const response = await api.post<GenerateVideoNoteResponse>("/notes/generate", {
        video_id: params.videoId,
        context_mode: params.contextMode ?? "auto",
        instruction: params.instruction ?? "",
        learner_profile: params.learnerProfile ?? "",
        max_parts: params.maxParts,
    });
    return response.data;
};

export interface TaskStatusResponse {
    id: string;
    type: string;
    content_id: string;
    status: "pending" | "processing" | "ready" | "error";
    progress: number;
    result_path: string | null;
    error: string | null;
    metadata: unknown;
    created_at: string;
    updated_at: string;
}

export const getJobStatus = async (taskId: string) => {
    const response = await api.get<TaskStatusResponse>(`/tasks/${taskId}`);
    return response.data;
};

// Ask tab: video question answering with contextual items

export interface AskResponse {
    answer: string;
}

export interface AskConversationSummary {
    id: string;
    title: string;
    created_at: string | null;
    updated_at: string | null;
    last_message_preview?: string;
}

export interface AskConversation {
    id: string;
    title: string;
    created_at: string | null;
    updated_at: string | null;
    messages: AskMessage[];
}

export interface ListAskConversationsResponse {
    video_id: string;
    conversations: AskConversationSummary[];
}

export interface AskConversationResponse {
    video_id: string;
    conversation: AskConversation;
}

export const listAskConversations = async (videoId: string) => {
    const response = await api.get<ListAskConversationsResponse>("/conversations", {
        params: { video_id: videoId },
    });
    return response.data;
};

export const createAskConversation = async (videoId: string, title?: string) => {
    const response = await api.post<AskConversationResponse>("/conversations", {
        video_id: videoId,
        title,
    });
    return response.data;
};

export const getAskConversation = async (videoId: string, conversationId: string) => {
    const response = await api.get<AskConversationResponse>(`/conversations/${conversationId}`, {
        params: {
            video_id: videoId,
        },
    });
    return response.data;
};

export const deleteAskConversation = async (videoId: string, conversationId: string) => {
    await api.delete(`/conversations/${conversationId}`, {
        data: {
            video_id: videoId,
        },
    });
};

export const askVideoQuestion = async (params: {
    videoId: string;
    conversationId: string;
    message: string;
    context: AskContextItem[];
    learnerProfile?: string;
    subtitleContextWindowSeconds?: number;
}) => {
    const response = await api.post<AskResponse>(`/conversations/${params.conversationId}/messages`, {
        video_id: params.videoId,
        message: params.message,
        context: params.context,
        learner_profile: params.learnerProfile,
        subtitle_context_window_seconds: params.subtitleContextWindowSeconds,
    });
    return response.data;
};

export interface SummarizeContextResponse {
    summary: string;
}

export const summarizeContext = async (params: {
    context: AskContextItem[];
    learnerProfile?: string;
}) => {
    const response = await api.post<SummarizeContextResponse>("/summaries", {
        context: params.context,
        learner_profile: params.learnerProfile,
    });
    return response.data;
};

export interface DeleteContentResponse {
    deleted: boolean;
    removedFiles?: string[];
    removedDirs?: string[];
    error?: string;
}

export const deleteContent = async (contentId: string) => {
    const response = await api.delete<DeleteContentResponse>(`/content/${contentId}`);
    return response.data;
};

export interface Live2DModel {
    name: string;
    path: string;
}

export const getLive2DModels = async () => {
    const response = await api.get<Live2DModel[]>("/live2d/models");
    return response.data;
};

export interface LLMModelInfo {
    name: string;
    model: string;
    provider: string;
}

export interface LLMModelsResponse {
    models: LLMModelInfo[];
    task_models: Record<string, string>;
    default: string;
}

export const getLLMModels = async () => {
    const response = await api.get<LLMModelsResponse>("/config/llm-models");
    return response.data;
};

export interface TTSProviderInfo {
    name: string;
    provider: string;
}

export interface TTSProvidersResponse {
    providers: TTSProviderInfo[];
    task_models: Record<string, string>;
    // Backward compatibility
    task_providers: Record<string, string>;
    default: string;
}

export const getTTSProviders = async () => {
    const response = await api.get<TTSProvidersResponse>("/config/tts-models");
    return response.data;
};

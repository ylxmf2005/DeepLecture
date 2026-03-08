/**
 * Content APIs - Upload, import, rename, delete content
 */

import { api, API_BASE_URL } from "./client";
import { withAIOverrides } from "./ai-overrides";
import type {
    ContentItem,
    ContentListResponse,
    UploadResponse,
    ImportResponse,
    RenameResponse,
    DeleteContentResponse,
    SlideLectureGenerationResponse,
} from "./types";

export interface DownloadVideoOptions {
    audioTrack?: string | null;
    burnSourceSubtitle?: boolean;
    burnTargetSubtitle?: boolean;
    sourceLanguage?: string;
    targetLanguage?: string;
}

export const uploadContent = async (
    file: File,
    options?: { projectId?: string | null }
): Promise<UploadResponse> => {
    const formData = new FormData();
    const isVideo = file.type.startsWith("video/");
    const isPdf = file.type === "application/pdf";

    if (isVideo) {
        formData.append("videos", file);
    } else if (isPdf) {
        formData.append("pdfs", file);
    } else {
        throw new Error("Unsupported file type");
    }

    // NOTE: FormData bypasses our snake_case interceptor; send wire-format field name.
    if (options?.projectId) {
        formData.append("project_id", options.projectId);
    }

    const response = await api.post<UploadResponse>("/content/upload", formData);
    return response.data;
};

export const uploadNoteImage = async (
    contentId: string,
    imageBlob: Blob
): Promise<{ contentId: string; filename: string; url: string }> => {
    const formData = new FormData();
    const timestamp = Date.now();
    const filename = `paste_${timestamp}.png`;
    formData.append("image", imageBlob, filename);
    // NOTE: FormData bypasses our snake_case interceptor; send wire-format field name.
    formData.append("content_id", contentId);

    const response = await api.post<{ contentId: string; filename: string; url: string }>(
        "/content/upload-note-image",
        formData
    );
    return response.data;
};

export const importVideoFromUrl = async (
    url: string,
    customName?: string,
    options?: { projectId?: string | null }
): Promise<ImportResponse> => {
    const response = await api.post<ImportResponse>("/content/import-url", {
        url,
        customName,
        ...(options?.projectId ? { projectId: options.projectId } : {}),
    });
    return response.data;
};

export const renameContent = async (
    contentId: string,
    newName: string
): Promise<RenameResponse> => {
    const response = await api.post<RenameResponse>(`/content/${contentId}/rename`, {
        newName,
    });
    return response.data;
};

export interface GenerateSlideLectureOptions {
    sourceLanguage: string;
    targetLanguage: string;
    ttsLanguage?: "source" | "target";
    force?: boolean;
}

export const generateSlideLecture = async (
    contentId: string,
    options: GenerateSlideLectureOptions
): Promise<SlideLectureGenerationResponse> => {
    const response = await api.post<SlideLectureGenerationResponse>(
        `/content/${contentId}/generate-video`,
        withAIOverrides({
            source_language: options.sourceLanguage,
            target_language: options.targetLanguage,
            tts_language: options.ttsLanguage ?? "source",
            force: options.force ?? false,
        })
    );
    return response.data;
};

export const getContentMetadata = async (contentId: string): Promise<ContentItem> => {
    const response = await api.get<ContentItem>(`/content/${contentId}`);
    return response.data;
};

export const listContent = async (
    options?: { projectId?: string | null }
): Promise<ContentListResponse> => {
    const params = new URLSearchParams();
    if (options?.projectId !== undefined && options.projectId !== null) {
        // NOTE: URLSearchParams bypasses our camelCase interceptor; send wire-format key.
        params.set("project_id", options.projectId);
    }
    const query = params.toString();
    const url = query ? `/content/list?${query}` : "/content/list";
    const response = await api.get<ContentListResponse>(url);
    return response.data;
};

export const deleteContent = async (contentId: string): Promise<DeleteContentResponse> => {
    const response = await api.delete<DeleteContentResponse>(`/content/${contentId}`);
    return response.data;
};

export const buildVideoDownloadUrl = (
    contentId: string,
    options: DownloadVideoOptions = {}
): string => {
    const params = new URLSearchParams();
    const audioTrack = options.audioTrack && options.audioTrack.trim() ? options.audioTrack.trim() : "original";

    params.set("audio_track", audioTrack);
    params.set("burn_source_subtitle", options.burnSourceSubtitle ? "1" : "0");
    params.set("burn_target_subtitle", options.burnTargetSubtitle ? "1" : "0");

    if (options.sourceLanguage && options.sourceLanguage.trim()) {
        params.set("source_language", options.sourceLanguage.trim());
    }
    if (options.targetLanguage && options.targetLanguage.trim()) {
        params.set("target_language", options.targetLanguage.trim());
    }

    return `${API_BASE_URL}/api/content/${encodeURIComponent(contentId)}/video/download?${params.toString()}`;
};

"use client";

import { create } from "zustand";
import { api } from "@/lib/api";
import { logger } from "@/shared/infrastructure";
import { toError, getErrorMessage } from "@/lib/utils/errorUtils";
import type { PdfFile, VideoFile } from "@/components/video/upload/types";
import { isAllowedVideo } from "@/components/video/upload/constants";

const log = logger.scope("UploadQueueStore");

interface UploadQueueState {
    pdfFiles: PdfFile[];
    videoFiles: VideoFile[];
    pdfCustomName: string;
    videoCustomName: string;
    uploadingPdf: boolean;
    uploadingVideo: boolean;
    uploadingUrl: boolean;
    error: string | null;

    // Actions
    addFiles: (files: File[]) => { rejected: string[] };
    removePdfFile: (id: string) => void;
    removeVideoFile: (id: string) => void;
    reorderPdfFiles: (oldIndex: number, newIndex: number) => void;
    reorderVideoFiles: (oldIndex: number, newIndex: number) => void;
    setPdfCustomName: (name: string) => void;
    setVideoCustomName: (name: string) => void;
    submitPdfs: (onSuccess: () => void) => Promise<void>;
    submitVideos: (onSuccess: () => void) => Promise<void>;
    importUrl: (url: string, customName: string, onSuccess: () => void) => Promise<void>;
    clearError: () => void;
    setError: (error: string | null) => void;
    reset: () => void;
}

const generateId = () => `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

export const useUploadQueueStore = create<UploadQueueState>()((set, get) => ({
    pdfFiles: [],
    videoFiles: [],
    pdfCustomName: "",
    videoCustomName: "",
    uploadingPdf: false,
    uploadingVideo: false,
    uploadingUrl: false,
    error: null,

    addFiles: (files: File[]) => {
        const state = get();
        const rejected: string[] = [];

        // Categorize files by type
        const pdfs = files.filter(f => f.type === "application/pdf");
        const videos = files.filter(isAllowedVideo);
        const unsupported = files.filter(f => f.type !== "application/pdf" && !isAllowedVideo(f));

        if (unsupported.length > 0) {
            rejected.push(`${unsupported.length} file(s) have unsupported format (only PDF, MP4, WebM, MOV allowed)`);
        }

        // Convert to internal format
        const validPdfs: PdfFile[] = pdfs.map(file => ({
            id: generateId(),
            file,
            name: file.name,
            size: file.size,
        }));

        const validVideos: VideoFile[] = videos.map(file => ({
            id: generateId(),
            file,
            name: file.name,
            size: file.size,
        }));

        // Update state
        set((s) => {
            const newPdfFiles = [...s.pdfFiles, ...validPdfs];
            const newVideoFiles = [...s.videoFiles, ...validVideos];

            // Set default names from first file if not already set
            let newPdfCustomName = s.pdfCustomName;
            let newVideoCustomName = s.videoCustomName;

            if (!newPdfCustomName && validPdfs.length > 0) {
                newPdfCustomName = validPdfs[0].name.replace(/\.pdf$/i, "");
            }
            if (!newVideoCustomName && validVideos.length > 0) {
                newVideoCustomName = validVideos[0].name.replace(/\.(mp4|webm|mov)$/i, "");
            }

            return {
                pdfFiles: newPdfFiles,
                videoFiles: newVideoFiles,
                pdfCustomName: newPdfCustomName,
                videoCustomName: newVideoCustomName,
                error: rejected.length > 0 ? rejected.join(". ") : null,
            };
        });

        return { rejected };
    },

    removePdfFile: (id: string) => {
        set((s) => {
            const newFiles = s.pdfFiles.filter(pdf => pdf.id !== id);
            return {
                pdfFiles: newFiles,
                pdfCustomName: newFiles.length === 0 ? "" : s.pdfCustomName,
            };
        });
    },

    removeVideoFile: (id: string) => {
        set((s) => {
            const newFiles = s.videoFiles.filter(video => video.id !== id);
            return {
                videoFiles: newFiles,
                videoCustomName: newFiles.length === 0 ? "" : s.videoCustomName,
            };
        });
    },

    reorderPdfFiles: (oldIndex: number, newIndex: number) => {
        set((s) => {
            const len = s.pdfFiles.length;
            // Bounds check: no-op if indices are invalid
            if (len === 0 || oldIndex < 0 || oldIndex >= len || newIndex < 0 || newIndex >= len || oldIndex === newIndex) {
                return s;
            }
            const newFiles = [...s.pdfFiles];
            const [removed] = newFiles.splice(oldIndex, 1);
            newFiles.splice(newIndex, 0, removed);
            return { pdfFiles: newFiles };
        });
    },

    reorderVideoFiles: (oldIndex: number, newIndex: number) => {
        set((s) => {
            const len = s.videoFiles.length;
            // Bounds check: no-op if indices are invalid
            if (len === 0 || oldIndex < 0 || oldIndex >= len || newIndex < 0 || newIndex >= len || oldIndex === newIndex) {
                return s;
            }
            const newFiles = [...s.videoFiles];
            const [removed] = newFiles.splice(oldIndex, 1);
            newFiles.splice(newIndex, 0, removed);
            return { videoFiles: newFiles };
        });
    },

    setPdfCustomName: (name: string) => set({ pdfCustomName: name }),
    setVideoCustomName: (name: string) => set({ videoCustomName: name }),

    submitPdfs: async (onSuccess: () => void) => {
        const state = get();
        if (state.pdfFiles.length === 0 || state.uploadingPdf) return;

        set({ uploadingPdf: true, error: null });

        try {
            const formData = new FormData();
            state.pdfFiles.forEach((pdfFile) => {
                formData.append("pdfs", pdfFile.file);
            });
            formData.append("custom_name", state.pdfCustomName || state.pdfFiles[0].name.replace(/\.pdf$/i, ""));

            await api.post("/content/upload", formData);

            set({ pdfFiles: [], pdfCustomName: "", uploadingPdf: false });
            onSuccess();
        } catch (err) {
            log.error("Failed to upload PDFs", toError(err), { fileCount: state.pdfFiles.length });
            set({ error: "Failed to upload PDFs. Please try again.", uploadingPdf: false });
        }
    },

    submitVideos: async (onSuccess: () => void) => {
        const state = get();
        if (state.videoFiles.length === 0 || state.uploadingVideo) return;

        set({ uploadingVideo: true, error: null });

        try {
            const formData = new FormData();
            state.videoFiles.forEach((videoFile) => {
                formData.append("videos", videoFile.file);
            });
            formData.append("custom_name", state.videoCustomName || state.videoFiles[0].name.replace(/\.(mp4|webm|mov)$/i, ""));

            await api.post("/content/upload", formData);

            set({ videoFiles: [], videoCustomName: "", uploadingVideo: false });
            onSuccess();
        } catch (err) {
            log.error("Failed to upload videos", toError(err), { fileCount: state.videoFiles.length });
            set({ error: "Failed to upload videos. Please try again.", uploadingVideo: false });
        }
    },

    importUrl: async (url: string, customName: string, onSuccess: () => void) => {
        if (!url || get().uploadingUrl) return;

        set({ uploadingUrl: true, error: null });

        try {
            const { importVideoFromUrl } = await import("@/lib/api");
            await importVideoFromUrl(url, customName || undefined);
            set({ uploadingUrl: false });
            onSuccess();
        } catch (err) {
            log.error("Failed to import video from URL", toError(err), { url });
            const message = getErrorMessage(err, "Failed to import video. Please check the URL and try again.");
            set({ error: message, uploadingUrl: false });
        }
    },

    clearError: () => set({ error: null }),
    setError: (error: string | null) => set({ error }),

    reset: () => set({
        pdfFiles: [],
        videoFiles: [],
        pdfCustomName: "",
        videoCustomName: "",
        uploadingPdf: false,
        uploadingVideo: false,
        uploadingUrl: false,
        error: null,
    }),
}));

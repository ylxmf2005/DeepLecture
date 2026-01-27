"use client";

/**
 * Video page event handlers.
 *
 * This file intentionally stays self-contained.
 * The earlier refactor to `./handlers/*` was incomplete (no module entry),
 * causing Next.js to fail module resolution at runtime.
 */

import { useCallback } from "react";
import type { Dispatch, RefObject, SetStateAction } from "react";

import {
    deleteVoiceover,
    enhanceAndTranslate,
    explainSlide,
    generateSlideLecture,
    generateSubtitles,
    generateTimeline,
    generateVoiceover,
    listVoiceovers,
    uploadContent,
} from "@/lib/api";
import type { SubtitleSource, TimelineEntry, VoiceoverEntry } from "@/lib/api";
import type { ProcessingAction } from "./useVideoPageState";
import type { AskContextItem } from "@/lib/askTypes";
import type { Subtitle } from "@/lib/srt";
import type { CrepeEditor } from "@/components/MarkdownNoteEditor";

export interface UseVideoPageHandlersOptions {
    videoId: string;
    originalLanguage: string;
    /**
     * Target language for all AI outputs (translations, timelines, explanations, notes).
     * Backward compatible aliases:
     * - `translatedLanguage` (older UI)
     * - `aiLanguage` (older UI)
     */
    targetLanguage?: string;
    translatedLanguage?: string;
    aiLanguage?: string;
    learnerProfile: string;
    subtitleContextWindowSeconds: number;
    /** Backward compatible alias: `subtitlesEn` */
    subtitlesSource?: Subtitle[];
    subtitlesEn?: Subtitle[];
    playerSubtitles: Subtitle[];
    voiceoverName: string;
    noteEditorRef: RefObject<CrepeEditor | null>;

    // State setters
    setProcessing: (processing: boolean) => void;
    setProcessingAction: (action: ProcessingAction) => void;
    setProcessingTaskId?: (taskId: string | null) => void;
    setRefreshExplanations: (fn: (prev: number) => number) => void;
    setVoiceoverProcessing: (source: SubtitleSource | null) => void;
    setVoiceovers: Dispatch<SetStateAction<VoiceoverEntry[]>>;
    selectedVoiceoverId: string | null;
    setSelectedVoiceoverId: (id: string | null) => void;
    setTimelineLoading: (loading: boolean) => void;
    setTimelineEntries: Dispatch<SetStateAction<TimelineEntry[]>>;
    setAskContext: Dispatch<SetStateAction<AskContextItem[]>>;
    setDeckStore: (videoId: string, deck: { id: string; name: string }) => void;

    // Content state
    hasSubtitles: boolean;
    hasEnhancedSubtitles: boolean;
}

export interface UseVideoPageHandlersReturn {
    handleCapture: (timestamp: number, imagePath: string) => Promise<void>;
    handleGenerateSubtitles: () => Promise<void>;
    handleTranslateSubtitles: () => Promise<void>;
    handleGenerateTimeline: () => Promise<void>;
    handleGenerateSlideLecture: (force?: boolean) => Promise<void>;
    handleGenerateVoiceover: (source: SubtitleSource) => Promise<void>;
    handleDeleteVoiceover: (voiceoverId: string) => Promise<void>;
    handleUpdateVoiceover: (voiceoverId: string, name: string) => Promise<void>;
    handleAddToAsk: (item: AskContextItem) => void;
    handleRemoveFromAsk: (id: string) => void;
    handleAddToNotes: (markdown: string) => void;
    handleAskAtTime: (time: number) => Promise<void>;
    handleAddNoteAtTime: (time: number) => void;
    handleUploadSlide: (file: File) => Promise<void>;
    buildSubtitleContextAroundTime: (time: number) => { text: string; startTime: number };
}

export function useVideoPageHandlers(options: UseVideoPageHandlersOptions): UseVideoPageHandlersReturn {
    const {
        videoId,
        originalLanguage,
        learnerProfile,
        subtitleContextWindowSeconds,
        voiceoverName,
        noteEditorRef,
        setProcessing,
        setProcessingAction,
        setProcessingTaskId,
        setRefreshExplanations,
        setVoiceoverProcessing,
        setVoiceovers,
        selectedVoiceoverId,
        setSelectedVoiceoverId,
        setTimelineLoading,
        setTimelineEntries,
        setAskContext,
        setDeckStore,
        hasSubtitles,
        hasEnhancedSubtitles,
    } = options;

    const targetLanguage = options.targetLanguage ?? options.translatedLanguage ?? options.aiLanguage ?? "";
    const subtitlesSource = options.subtitlesSource ?? options.subtitlesEn ?? [];

    const buildSubtitleContextAroundTime = useCallback(
        (time: number) => {
            const windowSeconds = Math.max(0, subtitleContextWindowSeconds);
            const start = time - windowSeconds;
            const end = time + windowSeconds;

            const nearby = subtitlesSource.filter((s) => s.endTime >= start && s.startTime <= end);
            const text = nearby.map((s) => s.text).join("\n").trim();
            const startTime = nearby.length > 0 ? nearby[0].startTime : time;

            return { text, startTime };
        },
        [subtitlesSource, subtitleContextWindowSeconds]
    );

    const handleGenerateSubtitles = useCallback(async () => {
        try {
            setProcessing(true);
            setProcessingAction("generate");

            const result = await generateSubtitles(videoId, originalLanguage, true);
            if (result.taskId && setProcessingTaskId) {
                setProcessingTaskId(result.taskId);
            }

            if (result.status === "ready") {
                setProcessing(false);
                setProcessingAction(null);
                setProcessingTaskId?.(null);
            }
        } catch {
            setProcessing(false);
            setProcessingAction(null);
            setProcessingTaskId?.(null);
        }
    }, [originalLanguage, setProcessing, setProcessingAction, setProcessingTaskId, videoId]);

    const handleTranslateSubtitles = useCallback(async () => {
        if (!hasSubtitles && !hasEnhancedSubtitles) return;

        try {
            setProcessing(true);
            setProcessingAction("translate");

            const result = await enhanceAndTranslate(videoId, targetLanguage, true);
            if (result.taskId && setProcessingTaskId) {
                setProcessingTaskId(result.taskId);
            }

            if (result.status === "ready") {
                setProcessing(false);
                setProcessingAction(null);
                setProcessingTaskId?.(null);
            }
        } catch {
            setProcessing(false);
            setProcessingAction(null);
            setProcessingTaskId?.(null);
        }
    }, [
        hasEnhancedSubtitles,
        hasSubtitles,
        setProcessing,
        setProcessingAction,
        setProcessingTaskId,
        targetLanguage,
        videoId,
    ]);

    const handleGenerateTimeline = useCallback(async () => {
        try {
            setProcessing(true);
            setProcessingAction("timeline");
            setTimelineLoading(true);

            const result = await generateTimeline(videoId, targetLanguage, true, learnerProfile);
            if (result.taskId && setProcessingTaskId) {
                setProcessingTaskId(result.taskId);
            }

            if (result.status === "ready") {
                setTimelineEntries(result.timeline ?? []);
                setTimelineLoading(false);
                setProcessing(false);
                setProcessingAction(null);
                setProcessingTaskId?.(null);
            }
        } catch {
            setTimelineLoading(false);
            setProcessing(false);
            setProcessingAction(null);
            setProcessingTaskId?.(null);
        }
    }, [
        learnerProfile,
        setProcessing,
        setProcessingAction,
        setProcessingTaskId,
        setTimelineEntries,
        setTimelineLoading,
        targetLanguage,
        videoId,
    ]);

    const handleGenerateSlideLecture = useCallback(
        async (force: boolean = false) => {
            try {
                setProcessing(true);
                setProcessingAction("video");

                const result = await generateSlideLecture(videoId, force);
                if (result.taskId && setProcessingTaskId) {
                    setProcessingTaskId(result.taskId);
                }

                if (result.status === "ready") {
                    setProcessing(false);
                    setProcessingAction(null);
                    setProcessingTaskId?.(null);
                }
            } catch {
                setProcessing(false);
                setProcessingAction(null);
                setProcessingTaskId?.(null);
            }
        },
        [setProcessing, setProcessingAction, setProcessingTaskId, videoId]
    );

    const handleUploadSlide = useCallback(
        async (file: File) => {
            const uploaded = await uploadContent(file);
            if (uploaded.contentType !== "slide") return;
            setDeckStore(videoId, { id: uploaded.contentId, name: uploaded.filename });
        },
        [setDeckStore, videoId]
    );

    const handleCapture = useCallback(
        async (timestamp: number, imagePath: string) => {
            await explainSlide(videoId, imagePath, timestamp, learnerProfile, subtitleContextWindowSeconds);
            setRefreshExplanations((prev) => prev + 1);
        },
        [learnerProfile, setRefreshExplanations, subtitleContextWindowSeconds, videoId]
    );

    const handleGenerateVoiceover = useCallback(
        async (source: SubtitleSource) => {
            try {
                setVoiceoverProcessing(source);
                await generateVoiceover(videoId, source, voiceoverName, targetLanguage);
            } catch {
                setVoiceoverProcessing(null);
            }
        },
        [setVoiceoverProcessing, targetLanguage, videoId, voiceoverName]
    );

    const handleDeleteVoiceover = useCallback(
        async (voiceoverId: string) => {
            await deleteVoiceover(videoId, voiceoverId);
            const data = await listVoiceovers(videoId);
            setVoiceovers(data.voiceovers ?? []);
            if (selectedVoiceoverId === voiceoverId) {
                setSelectedVoiceoverId(null);
            }
        },
        [selectedVoiceoverId, setSelectedVoiceoverId, setVoiceovers, videoId]
    );

    const handleUpdateVoiceover = useCallback(
        async (voiceoverId: string, name: string) => {
            // Backend currently has no rename endpoint; keep UI consistent locally.
            setVoiceovers((prev) =>
                prev.map((v) => (v.id === voiceoverId ? { ...v, name, updatedAt: new Date().toISOString() } : v))
            );
        },
        [setVoiceovers]
    );

    const handleAddToAsk = useCallback(
        (item: AskContextItem) => {
            setAskContext((prev) => {
                if (prev.some((x) => x.id === item.id)) return prev;
                return [...prev, item];
            });
        },
        [setAskContext]
    );

    const handleRemoveFromAsk = useCallback(
        (id: string) => {
            setAskContext((prev) => prev.filter((x) => x.id !== id));
        },
        [setAskContext]
    );

    const handleAddToNotes = useCallback(
        (markdown: string) => {
            const editor = noteEditorRef.current;
            if (!editor) return;
            const current = editor.getMarkdown?.() ?? "";
            const next = current.trim().length > 0 ? `${current.trim()}\n\n${markdown.trim()}\n` : `${markdown.trim()}\n`;
            editor.setMarkdown(next);
        },
        [noteEditorRef]
    );

    const handleAskAtTime = useCallback(
        async (time: number) => {
            const ctx = buildSubtitleContextAroundTime(time);
            if (!ctx.text) return;
            handleAddToAsk({
                type: "subtitle",
                id: `subtitle@${ctx.startTime.toFixed(3)}`,
                text: ctx.text,
                startTime: ctx.startTime,
            });
        },
        [buildSubtitleContextAroundTime, handleAddToAsk]
    );

    const handleAddNoteAtTime = useCallback(
        (time: number) => {
            const ctx = buildSubtitleContextAroundTime(time);
            const title = `### ${new Date(time * 1000).toISOString().slice(11, 19)}\n`;
            const body = ctx.text ? `${ctx.text}\n` : "";
            handleAddToNotes(`${title}\n${body}`.trim());
        },
        [buildSubtitleContextAroundTime, handleAddToNotes]
    );

    return {
        handleCapture,
        handleGenerateSubtitles,
        handleTranslateSubtitles,
        handleGenerateTimeline,
        handleGenerateSlideLecture,
        handleGenerateVoiceover,
        handleDeleteVoiceover,
        handleUpdateVoiceover,
        handleAddToAsk,
        handleRemoveFromAsk,
        handleAddToNotes,
        handleAskAtTime,
        handleAddNoteAtTime,
        handleUploadSlide,
        buildSubtitleContextAroundTime,
    };
}

        learnerProfile,
        subtitleContextWindowSeconds,
        subtitlesSource,
        playerSubtitles,
        voiceoverName,
        noteEditorRef,
        setProcessing,
        setProcessingAction,
        setProcessingTaskId,
        setRefreshExplanations,
        setVoiceoverProcessing,
        setVoiceovers,
        selectedVoiceoverId,
        setSelectedVoiceoverId,
        setTimelineLoading,
        setTimelineEntries,
        setAskContext,
        setDeckStore,
        hasSubtitles,
        hasEnhancedSubtitles,
    } = options;

    // Subtitle operations
    const { handleGenerateSubtitles, handleTranslateSubtitles } = useSubtitleHandlers({
        videoId,
        originalLanguage,
        translatedLanguage: targetLanguage,
        hasSubtitles,
        hasEnhancedSubtitles,
        setProcessing,
        setProcessingAction,
        setProcessingTaskId,
    });

    // Timeline operations
    const { handleGenerateTimeline } = useTimelineHandlers({
        videoId,
        originalLanguage,
        targetLanguage,
        learnerProfile,
        hasSubtitles,
        setProcessing,
        setProcessingAction,
        setTimelineLoading,
        setTimelineEntries,
    });

    // Slide operations
    const { handleCapture, handleGenerateSlideLecture, handleUploadSlide } = useSlideHandlers({
        videoId,
        sourceLanguage: originalLanguage,
        targetLanguage,
        learnerProfile,
        subtitleContextWindowSeconds,
        setProcessing,
        setProcessingAction,
        setRefreshExplanations,
        setDeckStore,
    });

    // Voiceover operations
    const { handleGenerateVoiceover, handleDeleteVoiceover, handleUpdateVoiceover } = useVoiceoverHandlers({
        videoId,
        voiceoverName,
        originalLanguage,
        translatedLanguage: targetLanguage,
        selectedVoiceoverId,
        setVoiceoverProcessing,
        setVoiceovers,
        setSelectedVoiceoverId,
    });

    // Content operations (Ask + Notes)
    const {
        handleAddToAsk,
        handleRemoveFromAsk,
        handleAddToNotes,
        handleAskAtTime,
        handleAddNoteAtTime,
        buildSubtitleContextAroundTime,
    } = useContentHandlers({
        videoId,
        subtitleContextWindowSeconds,
        subtitlesSource,
        playerSubtitles,
        noteEditorRef,
        setAskContext,
    });

    return {
        handleCapture,
        handleGenerateSubtitles,
        handleTranslateSubtitles,
        handleGenerateTimeline,
        handleGenerateSlideLecture,
        handleGenerateVoiceover,
        handleDeleteVoiceover,
        handleUpdateVoiceover,
        handleAddToAsk,
        handleRemoveFromAsk,
        handleAddToNotes,
        handleAskAtTime,
        handleAddNoteAtTime,
        handleUploadSlide,
        buildSubtitleContextAroundTime,
    };
}

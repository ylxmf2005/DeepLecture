"use client";

/**
 * Composite hook that composes all video page handlers.
 * Maintains backward compatibility while delegating to focused domain hooks.
 *
 * @see ./handlers/ for individual domain hooks
 */

import type { SubtitleSource, VoiceoverEntry, TimelineEntry } from "@/lib/api";
import type { ProcessingAction } from "./useVideoPageState";
import type { AskContextItem } from "@/lib/askTypes";
import type { Subtitle } from "@/lib/srt";
import type { CrepeEditor } from "@/components/editor/MarkdownNoteEditor";

import {
    useSubtitleHandlers,
    useTimelineHandlers,
    useSlideHandlers,
    useVoiceoverHandlers,
    useContentHandlers,
} from "./handlers";

export interface UseVideoPageHandlersOptions {
    videoId: string;
    originalLanguage: string;
    detectedSourceLanguage?: string | null;
    /** Target language for all AI outputs (translations, timelines, explanations, notes) */
    targetLanguage: string;
    learnerProfile: string;
    subtitleContextWindowSeconds: number;
    subtitlesSource: Subtitle[];
    playerSubtitles: Subtitle[];
    voiceoverName: string;
    noteEditorRef: React.RefObject<CrepeEditor | null>;

    // State setters
    setProcessing: (processing: boolean) => void;
    setProcessingAction: (action: ProcessingAction) => void;
    setRefreshExplanations: (fn: (prev: number) => number) => void;
    setVoiceoverProcessing: (source: SubtitleSource | null) => void;
    setVoiceovers: (voiceovers: VoiceoverEntry[]) => void;
    selectedVoiceoverId: string | null;
    setSelectedVoiceoverId: (id: string | null) => void;
    setTimelineLoading: (loading: boolean) => void;
    setTimelineEntries: (entries: TimelineEntry[]) => void;
    setAskContext: React.Dispatch<React.SetStateAction<AskContextItem[]>>;
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

/**
 * Composite hook for video page event handlers.
 * Delegates to domain-specific hooks for better separation of concerns.
 */
export function useVideoPageHandlers(options: UseVideoPageHandlersOptions): UseVideoPageHandlersReturn {
    const {
        videoId,
        originalLanguage,
        detectedSourceLanguage,
        targetLanguage,
        learnerProfile,
        subtitleContextWindowSeconds,
        subtitlesSource,
        playerSubtitles,
        voiceoverName,
        noteEditorRef,
        setProcessing,
        setProcessingAction,
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
    });

    // Timeline operations
    const { handleGenerateTimeline } = useTimelineHandlers({
        videoId,
        originalLanguage,
        detectedSourceLanguage,
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
        detectedSourceLanguage,
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
        detectedSourceLanguage,
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

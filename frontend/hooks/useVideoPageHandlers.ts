"use client";

import { useCallback } from "react";
import {
    generateSubtitles,
    enhanceAndTranslate,
    explainSlide,
    captureSlide,
    generateVoiceover,
    listVoiceovers,
    generateTimeline,
    SubtitleSource,
    VoiceoverEntry,
    generateSlideLecture,
    uploadContent,
} from "@/lib/api";
import type { ProcessingAction } from "./useVideoPageState";
import type { AskContextItem } from "@/lib/askTypes";
import { formatTime } from "@/lib/timeFormat";
import type { Subtitle } from "@/lib/srt";
import { findSubtitleAtTime } from "@/lib/subtitleSearch";
import type { CrepeEditor } from "@/components/MarkdownNoteEditor";
import type { SidebarTabType } from "@/components/video";

export interface UseVideoPageHandlersOptions {
    videoId: string;
    originalLanguage: string;
    translatedLanguage: string;
    aiLanguage: string;
    learnerProfile: string;
    subtitleContextWindowSeconds: number;
    subtitlesEn: Subtitle[];
    playerSubtitles: Subtitle[];
    voiceoverName: string;
    noteEditorRef: React.RefObject<CrepeEditor | null>;

    // State setters
    setProcessing: (processing: boolean) => void;
    setProcessingAction: (action: ProcessingAction) => void;
    setActiveTab: (tab: SidebarTabType) => void;
    setRefreshExplanations: (fn: (prev: number) => number) => void;
    setVoiceoverProcessing: (source: SubtitleSource | null) => void;
    setVoiceovers: (voiceovers: VoiceoverEntry[]) => void;
    setTimelineLoading: (loading: boolean) => void;
    setTimelineEntries: (entries: import("@/lib/api").TimelineEntry[]) => void;
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
    handleAddToAsk: (item: AskContextItem) => void;
    handleRemoveFromAsk: (id: string) => void;
    handleAddToNotes: (markdown: string) => void;
    handleAskAtTime: (time: number) => Promise<void>;
    handleAddNoteAtTime: (time: number) => void;
    handleUploadSlide: (file: File) => Promise<void>;
    buildSubtitleContextAroundTime: (time: number) => { text: string; startTime: number };
}

/**
 * Hook containing event handlers for the video page.
 * Extracted to reduce the main component size.
 */
export function useVideoPageHandlers({
    videoId,
    originalLanguage,
    translatedLanguage,
    aiLanguage,
    learnerProfile,
    subtitleContextWindowSeconds,
    subtitlesEn,
    playerSubtitles,
    voiceoverName,
    noteEditorRef,
    setProcessing,
    setProcessingAction,
    setActiveTab,
    setRefreshExplanations,
    setVoiceoverProcessing,
    setVoiceovers,
    setTimelineLoading,
    setTimelineEntries,
    setAskContext,
    setDeckStore,
    hasSubtitles,
    hasEnhancedSubtitles,
}: UseVideoPageHandlersOptions): UseVideoPageHandlersReturn {

    const buildSubtitleContextAroundTime = useCallback(
        (time: number): { text: string; startTime: number } => {
            const windowSeconds = subtitleContextWindowSeconds > 0 ? subtitleContextWindowSeconds : 30;
            const sourceSubs = subtitlesEn.length > 0 ? subtitlesEn : playerSubtitles;

            if (!sourceSubs || sourceSubs.length === 0) {
                return {
                    text: `Content around ${formatTime(time)} in the lecture.`,
                    startTime: time,
                };
            }

            const windowStart = Math.max(0, time - windowSeconds);
            const windowEnd = time + windowSeconds;

            const inWindow = sourceSubs.filter(
                (sub) => sub.endTime >= windowStart && sub.startTime <= windowEnd
            );

            if (inWindow.length === 0) {
                const fallback = findSubtitleAtTime(time, sourceSubs);
                if (!fallback) {
                    return {
                        text: `Content around ${formatTime(time)} in the lecture.`,
                        startTime: time,
                    };
                }
                return {
                    text: fallback.text,
                    startTime: fallback.startTime,
                };
            }

            const lines = inWindow.map(
                (sub) => `[${formatTime(sub.startTime)}] ${sub.text}`
            );
            const text = lines.join("\n");
            const startTime = inWindow[0]?.startTime ?? time;

            return { text, startTime };
        },
        [subtitleContextWindowSeconds, subtitlesEn, playerSubtitles]
    );

    const handleCapture = useCallback(
        async (timestamp: number, imagePath: string) => {
            try {
                setActiveTab("explanations");
                await explainSlide(
                    videoId,
                    imagePath,
                    timestamp,
                    learnerProfile || undefined,
                    subtitleContextWindowSeconds
                );
                setRefreshExplanations((prev) => prev + 1);
            } catch (error) {
                console.error("Failed to generate explanation:", error);
            }
        },
        [videoId, learnerProfile, subtitleContextWindowSeconds, setActiveTab, setRefreshExplanations]
    );

    const handleGenerateSubtitles = useCallback(async () => {
        try {
            setProcessing(true);
            setProcessingAction("generate");
            const result = await generateSubtitles(videoId, originalLanguage, true);

            if (result.status === "ready") {
                setProcessing(false);
                setProcessingAction(null);
            }
        } catch (error) {
            console.error("Failed to generate subtitles:", error);
            setProcessing(false);
            setProcessingAction(null);
        }
    }, [videoId, originalLanguage, setProcessing, setProcessingAction]);

    const handleTranslateSubtitles = useCallback(async () => {
        if (!hasSubtitles && !hasEnhancedSubtitles) return;
        try {
            setProcessing(true);
            setProcessingAction("translate");
            const result = await enhanceAndTranslate(videoId, translatedLanguage, true);

            if (result.status === "ready") {
                setProcessing(false);
                setProcessingAction(null);
            }
        } catch (error) {
            console.error("Failed to enhance and translate subtitles:", error);
            setProcessing(false);
            setProcessingAction(null);
        }
    }, [videoId, translatedLanguage, hasSubtitles, hasEnhancedSubtitles, setProcessing, setProcessingAction]);

    const handleGenerateTimeline = useCallback(async () => {
        if (!hasSubtitles) return;

        try {
            setProcessing(true);
            setProcessingAction("timeline");
            setTimelineLoading(true);
            const data = await generateTimeline(
                videoId,
                aiLanguage,
                true,
                learnerProfile || undefined
            );
            setTimelineEntries(data.timeline || []);

            if (data.cached || (data.timeline && data.timeline.length > 0)) {
                setProcessing(false);
                setProcessingAction(null);
                setTimelineLoading(false);
            }
        } catch (error) {
            console.error("Failed to generate timeline:", error);
            setProcessing(false);
            setProcessingAction(null);
            setTimelineLoading(false);
        }
    }, [videoId, aiLanguage, learnerProfile, hasSubtitles, setProcessing, setProcessingAction, setTimelineLoading, setTimelineEntries]);

    const handleGenerateSlideLecture = useCallback(
        async (force: boolean = false) => {
            try {
                setProcessing(true);
                setProcessingAction("video");
                const result = await generateSlideLecture(videoId, force);

                if (result.status !== "processing") {
                    setProcessing(false);
                    setProcessingAction(null);
                }
            } catch (err) {
                console.error("Failed to generate slide lecture:", err);
                setProcessing(false);
                setProcessingAction(null);
            }
        },
        [videoId, setProcessing, setProcessingAction]
    );

    const handleGenerateVoiceover = useCallback(
        async (source: SubtitleSource) => {
            const name = voiceoverName.trim();
            if (!name) {
                alert("Please enter a name for this voiceover first.");
                return;
            }

            try {
                setVoiceoverProcessing(source);
                await generateVoiceover(videoId, source, name, translatedLanguage);

                const data = await listVoiceovers(videoId);
                setVoiceovers(data.voiceovers);
            } catch (error) {
                console.error("Failed to generate voiceover:", error);
            } finally {
                setVoiceoverProcessing(null);
            }
        },
        [videoId, voiceoverName, translatedLanguage, setVoiceoverProcessing, setVoiceovers]
    );

    const handleAddToAsk = useCallback(
        (item: AskContextItem) => {
            setAskContext((prev) => {
                if (prev.some((i) => i.id === item.id)) return prev;
                return [...prev, item];
            });
            setActiveTab("ask");
        },
        [setAskContext, setActiveTab]
    );

    const handleRemoveFromAsk = useCallback(
        (id: string) => {
            setAskContext((prev) => prev.filter((i) => i.id !== id));
        },
        [setAskContext]
    );

    const handleAddToNotes = useCallback(
        (markdown: string) => {
            const editor = noteEditorRef.current;
            if (!editor) {
                return;
            }

            if (typeof markdown !== "string") {
                return;
            }

            const newContent = markdown.trim();
            if (!newContent) {
                return;
            }

            try {
                const currentMarkdown = editor.getMarkdown();
                const prefix = currentMarkdown.trim().length > 0 ? "\n\n" : "";
                editor.setMarkdown(`${currentMarkdown}${prefix}${newContent}\n\n`);
            } catch (err) {
                console.error("Failed to add to notes:", err);
                const storageKey = `note-${window.location.pathname.split("/").pop() ?? "unknown"}`;
                const currentStored = localStorage.getItem(storageKey) ?? "";
                const storedPrefix = currentStored.trim().length > 0 ? "\n\n" : "";
                localStorage.setItem(storageKey, `${currentStored}${storedPrefix}${newContent}\n\n`);
                alert("Note saved to local storage. Please refresh the page to see it in the editor.");
            }
        },
        [noteEditorRef]
    );

    const handleAskAtTime = useCallback(
        async (time: number) => {
            const { text, startTime } = buildSubtitleContextAroundTime(time);

            try {
                const capture = await captureSlide(videoId, time);

                const screenshotItem: AskContextItem = {
                    type: "screenshot",
                    id: `screenshot-${Math.round(capture.timestamp * 1000)}`,
                    imageUrl: capture.image_url,
                    timestamp: capture.timestamp,
                    imagePath: capture.image_path,
                };

                const subtitleItem: AskContextItem = {
                    type: "subtitle",
                    id: `player-${startTime.toFixed(1)}`,
                    text,
                    startTime,
                };

                handleAddToAsk(screenshotItem);
                handleAddToAsk(subtitleItem);
            } catch (error) {
                console.error("Failed to capture slide for Ask context:", error);
                const subtitleItem: AskContextItem = {
                    type: "subtitle",
                    id: `player-${startTime.toFixed(1)}`,
                    text,
                    startTime,
                };
                handleAddToAsk(subtitleItem);
            }
        },
        [videoId, buildSubtitleContextAroundTime, handleAddToAsk]
    );

    const handleAddNoteAtTime = useCallback(
        (time: number) => {
            const sub = findSubtitleAtTime(time, playerSubtitles);
            const effectiveTime = sub ? sub.startTime : time;
            const label = formatTime(effectiveTime);
            const text =
                sub?.text && typeof sub.text === "string"
                    ? sub.text
                    : "Note about this moment in the lecture.";

            captureSlide(videoId, effectiveTime)
                .then((capture) => {
                    const parts = capture.image_path.split(/[\\/]/);
                    const name = parts[parts.length - 1] ?? "";
                    if (!name) {
                        const fallbackSnippet = `- [${label}] ${text}`;
                        handleAddToNotes(fallbackSnippet);
                        return;
                    }
                    const relPath = `../notes_assets/${videoId}/${name}`;
                    const snippet = `![${label}](${relPath})\n\n- [${label}] ${text}`;
                    handleAddToNotes(snippet);
                })
                .catch((error) => {
                    console.error("Failed to capture slide for notes:", error);
                    const fallbackSnippet = `- [${label}] ${text}`;
                    handleAddToNotes(fallbackSnippet);
                });
        },
        [videoId, playerSubtitles, handleAddToNotes]
    );

    const handleUploadSlide = useCallback(
        async (file: File) => {
            if (!videoId) return;

            try {
                const res = await uploadContent(file);
                if (res.contentType !== "slide") return;

                const value = {
                    id: res.contentId,
                    name: res.filename,
                };

                setDeckStore(videoId, value);
            } catch (error) {
                console.error("Failed to upload slide deck for video:", error);
            }
        },
        [videoId, setDeckStore]
    );

    return {
        handleCapture,
        handleGenerateSubtitles,
        handleTranslateSubtitles,
        handleGenerateTimeline,
        handleGenerateSlideLecture,
        handleGenerateVoiceover,
        handleAddToAsk,
        handleRemoveFromAsk,
        handleAddToNotes,
        handleAskAtTime,
        handleAddNoteAtTime,
        handleUploadSlide,
        buildSubtitleContextAroundTime,
    };
}

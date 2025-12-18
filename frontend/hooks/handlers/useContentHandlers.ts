"use client";

import { useCallback } from "react";
import { toast } from "sonner";
import { captureSlide } from "@/lib/api";
import type { AskContextItem } from "@/lib/askTypes";
import type { Subtitle } from "@/lib/srt";
import { formatTime } from "@/lib/timeFormat";
import { findSubtitleAtTime } from "@/lib/subtitleSearch";
import type { CrepeEditor } from "@/components/editor/MarkdownNoteEditor";
import { useTabLayoutStore, findTabPanel, type TabId } from "@/stores/tabLayoutStore";
import { logger } from "@/shared/infrastructure";

const log = logger.scope("ContentHandlers");

export interface UseContentHandlersOptions {
    videoId: string;
    subtitleContextWindowSeconds: number;
    subtitlesSource: Subtitle[];
    playerSubtitles: Subtitle[];
    noteEditorRef: React.RefObject<CrepeEditor | null>;
    setAskContext: React.Dispatch<React.SetStateAction<AskContextItem[]>>;
}

export interface UseContentHandlersReturn {
    handleAddToAsk: (item: AskContextItem) => void;
    handleRemoveFromAsk: (id: string) => void;
    handleAddToNotes: (markdown: string) => void;
    handleAskAtTime: (time: number) => Promise<void>;
    handleAddNoteAtTime: (time: number) => void;
    buildSubtitleContextAroundTime: (time: number) => { text: string; startTime: number };
}

/**
 * Handles Ask context and Notes content management.
 */
export function useContentHandlers({
    videoId,
    subtitleContextWindowSeconds,
    subtitlesSource,
    playerSubtitles,
    noteEditorRef,
    setAskContext,
}: UseContentHandlersOptions): UseContentHandlersReturn {
    const activateTab = useCallback((tabId: TabId) => {
        const { panels, setActiveTab } = useTabLayoutStore.getState();
        const panel = findTabPanel(panels, tabId);
        if (panel) setActiveTab(panel, tabId);
    }, []);

    const buildSubtitleContextAroundTime = useCallback(
        (time: number): { text: string; startTime: number } => {
            const windowSeconds = subtitleContextWindowSeconds > 0 ? subtitleContextWindowSeconds : 30;
            const sourceSubs = subtitlesSource.length > 0 ? subtitlesSource : playerSubtitles;

            if (!sourceSubs || sourceSubs.length === 0) {
                return { text: `Content around ${formatTime(time)} in the lecture.`, startTime: time };
            }

            const windowStart = Math.max(0, time - windowSeconds);
            const windowEnd = time + windowSeconds;
            const inWindow = sourceSubs.filter((sub) => sub.endTime >= windowStart && sub.startTime <= windowEnd);

            if (inWindow.length === 0) {
                const fallback = findSubtitleAtTime(time, sourceSubs);
                if (!fallback) {
                    return { text: `Content around ${formatTime(time)} in the lecture.`, startTime: time };
                }
                return { text: fallback.text, startTime: fallback.startTime };
            }

            const lines = inWindow.map((sub) => `[${formatTime(sub.startTime)}] ${sub.text}`);
            return { text: lines.join("\n"), startTime: inWindow[0]?.startTime ?? time };
        },
        [subtitleContextWindowSeconds, subtitlesSource, playerSubtitles]
    );

    const handleAddToAsk = useCallback(
        (item: AskContextItem) => {
            setAskContext((prev) => (prev.some((i) => i.id === item.id) ? prev : [...prev, item]));
            activateTab("ask");
        },
        [setAskContext, activateTab]
    );

    const handleRemoveFromAsk = useCallback(
        (id: string) => setAskContext((prev) => prev.filter((i) => i.id !== id)),
        [setAskContext]
    );

    const handleAddToNotes = useCallback(
        (markdown: string) => {
            const editor = noteEditorRef.current;
            if (!editor || typeof markdown !== "string") return;

            const newContent = markdown.trim();
            if (!newContent) return;

            try {
                const currentMarkdown = editor.getMarkdown();
                const prefix = currentMarkdown.trim().length > 0 ? "\n\n" : "";
                editor.setMarkdown(`${currentMarkdown}${prefix}${newContent}\n\n`);
            } catch (err) {
                log.warn("Failed to add to notes via editor, using localStorage fallback", { error: String(err) });
                const storageKey = `note-${videoId || "unknown"}`;
                const currentStored = localStorage.getItem(storageKey) ?? "";
                const storedPrefix = currentStored.trim().length > 0 ? "\n\n" : "";
                localStorage.setItem(storageKey, `${currentStored}${storedPrefix}${newContent}\n\n`);
                toast.info("Note saved to local storage. Refresh to see in editor.");
            }
        },
        [noteEditorRef, videoId]
    );

    const handleAskAtTime = useCallback(
        async (time: number) => {
            const { text, startTime } = buildSubtitleContextAroundTime(time);

            try {
                const capture = await captureSlide(videoId, time);
                handleAddToAsk({
                    type: "screenshot",
                    id: `screenshot-${Math.round(capture.timestamp * 1000)}`,
                    imageUrl: capture.imageUrl,
                    timestamp: capture.timestamp,
                    imagePath: capture.imagePath,
                });
                handleAddToAsk({ type: "subtitle", id: `player-${startTime.toFixed(1)}`, text, startTime });
            } catch {
                log.warn("Failed to capture slide for Ask, using subtitle only", { videoId, time });
                handleAddToAsk({ type: "subtitle", id: `player-${startTime.toFixed(1)}`, text, startTime });
            }
        },
        [videoId, buildSubtitleContextAroundTime, handleAddToAsk]
    );

    const handleAddNoteAtTime = useCallback(
        (time: number) => {
            const sub = findSubtitleAtTime(time, playerSubtitles);
            const effectiveTime = sub ? sub.startTime : time;
            const label = formatTime(effectiveTime);
            const text = sub?.text && typeof sub.text === "string" ? sub.text : "Note about this moment.";

            captureSlide(videoId, effectiveTime)
                .then((capture) => {
                    const parts = (capture.imagePath ?? capture.imageUrl).split(/[\\/]/);
                    const name = parts[parts.length - 1] ?? "";
                    if (!name) {
                        handleAddToNotes(`- [${label}] ${text}`);
                        return;
                    }
                    const relPath = `../notes_assets/${videoId}/${name}`;
                    handleAddToNotes(`![${label}](${relPath})\n\n- [${label}] ${text}`);
                })
                .catch(() => {
                    log.warn("Failed to capture slide for notes, using text fallback", { videoId, effectiveTime });
                    handleAddToNotes(`- [${label}] ${text}`);
                });
        },
        [videoId, playerSubtitles, handleAddToNotes]
    );

    return {
        handleAddToAsk,
        handleRemoveFromAsk,
        handleAddToNotes,
        handleAskAtTime,
        handleAddNoteAtTime,
        buildSubtitleContextAroundTime,
    };
}

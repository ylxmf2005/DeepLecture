"use client";

import { useRef, useCallback, useEffect } from "react";
import { getVideoNote, generateVideoNote } from "@/lib/api";
import { useNoteSettings } from "@/stores/useGlobalSettingsStore";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";
import { useTaskNotification } from "@/hooks/useTaskNotification";
import type { CrepeEditor } from "@/components/editor/MarkdownNoteEditor";

const log = logger.scope("NoteGeneration");

export interface UseNoteGenerationParams {
    videoId: string;
    targetLanguage: string;
    learnerProfile: string;
    generatingNote: boolean;
    setGeneratingNote: (generating: boolean) => void;
    confirm: (options: {
        title: string;
        message: string;
        confirmLabel: string;
        cancelLabel: string;
        variant?: "warning" | "danger" | "default";
    }) => Promise<boolean>;
}

export interface UseNoteGenerationReturn {
    noteEditorRef: React.MutableRefObject<CrepeEditor | null>;
    handleNoteEditorReady: (editor: CrepeEditor) => void;
    handleGenerateNote: () => Promise<void>;
}

/**
 * Hook to manage AI note generation via SSE task updates.
 * Triggers generation and listens for completion via generatingNote state
 * which is updated by useVideoPageState when SSE task completes.
 */
export function useNoteGeneration({
    videoId,
    targetLanguage,
    learnerProfile,
    generatingNote,
    setGeneratingNote,
    confirm,
}: UseNoteGenerationParams): UseNoteGenerationReturn {
    const noteEditorRef = useRef<CrepeEditor | null>(null);
    const pendingGeneratedNoteRef = useRef<string | null>(null);
    const noteSettings = useNoteSettings();
    const { notifyTaskComplete, notifyOperation } = useTaskNotification();
    // Track if we triggered the generation (vs page load with existing task)
    const didTriggerGenerationRef = useRef(false);
    // Track previous generatingNote state to detect completion
    const prevGeneratingNoteRef = useRef(generatingNote);

    const handleNoteEditorReady = useCallback((editor: CrepeEditor) => {
        noteEditorRef.current = editor;
        if (pendingGeneratedNoteRef.current !== null) {
            editor.setMarkdown(pendingGeneratedNoteRef.current);
            pendingGeneratedNoteRef.current = null;
        }
    }, []);

    // Load note content when generation completes (SSE updates generatingNote to false)
    useEffect(() => {
        const wasGenerating = prevGeneratingNoteRef.current;
        prevGeneratingNoteRef.current = generatingNote;

        // Only load note if: was generating → now not generating AND we triggered it
        if (wasGenerating && !generatingNote && didTriggerGenerationRef.current) {
            didTriggerGenerationRef.current = false;

            const loadNote = async () => {
                try {
                    const note = await getVideoNote(videoId);
                    const content = note.content || "";
                    const editor = noteEditorRef.current;
                    if (editor) {
                        editor.setMarkdown(content);
                    } else {
                        log.info("Editor not ready when note generation completed, deferring note apply", { videoId });
                        pendingGeneratedNoteRef.current = content;
                    }
                } catch (error) {
                    log.error("Failed to load note after generation", toError(error), { videoId });
                    notifyOperation("note_load", "error", toError(error).message);
                }
            };

            loadNote();
        }
    }, [generatingNote, notifyOperation, videoId]);

    const handleGenerateNote = useCallback(async () => {
        if (!videoId || generatingNote) return;

        const confirmed = await confirm({
            title: "Generate AI Note",
            message: "This will overwrite any existing notes you have written. Are you sure you want to continue?",
            confirmLabel: "Generate",
            cancelLabel: "Cancel",
            variant: "warning",
        });

        if (!confirmed) return;

        try {
            pendingGeneratedNoteRef.current = null;
            setGeneratingNote(true);
            didTriggerGenerationRef.current = true;

            const start = await generateVideoNote({ contentId: videoId, language: targetLanguage, contextMode: noteSettings.contextMode, learnerProfile });

            // If already ready (cached result), load immediately
            if (start.status === "ready" || !start.taskId) {
                const note = await getVideoNote(videoId);
                const content = note.content || "";
                const editor = noteEditorRef.current;
                if (editor) {
                    editor.setMarkdown(content);
                } else {
                    pendingGeneratedNoteRef.current = content;
                }
                notifyTaskComplete("note_generation", "ready");
                setGeneratingNote(false);
                didTriggerGenerationRef.current = false;
                return;
            }

            // Task submitted - SSE will notify completion via useVideoPageState
            // which will set generatingNote to false, triggering the useEffect above
            log.info("Note generation task submitted", { videoId, taskId: start.taskId });
        } catch (error) {
            log.error("Failed to start note generation", toError(error), { videoId });
            notifyTaskComplete("note_generation", "error", toError(error).message);
            setGeneratingNote(false);
            didTriggerGenerationRef.current = false;
        }
    }, [
        videoId,
        targetLanguage,
        learnerProfile,
        generatingNote,
        setGeneratingNote,
        confirm,
        noteSettings.contextMode,
        notifyTaskComplete,
    ]);

    return {
        noteEditorRef,
        handleNoteEditorReady,
        handleGenerateNote,
    };
}

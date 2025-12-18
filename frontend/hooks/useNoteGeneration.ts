"use client";

import { useRef, useCallback, useEffect } from "react";
import { toast } from "sonner";
import { getVideoNote, generateVideoNote } from "@/lib/api";
import { useNoteSettings } from "@/stores/useGlobalSettingsStore";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";
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
    const noteSettings = useNoteSettings();
    // Track if we triggered the generation (vs page load with existing task)
    const didTriggerGenerationRef = useRef(false);
    // Track previous generatingNote state to detect completion
    const prevGeneratingNoteRef = useRef(generatingNote);

    const handleNoteEditorReady = useCallback((editor: CrepeEditor) => {
        noteEditorRef.current = editor;
    }, []);

    // Load note content when generation completes (SSE updates generatingNote to false)
    useEffect(() => {
        const wasGenerating = prevGeneratingNoteRef.current;
        prevGeneratingNoteRef.current = generatingNote;

        // Only load note if: was generating → now not generating AND we triggered it
        if (wasGenerating && !generatingNote && didTriggerGenerationRef.current) {
            didTriggerGenerationRef.current = false;

            const loadNote = async () => {
                const editor = noteEditorRef.current;
                if (!editor) {
                    log.warn("Editor not ready when note generation completed", { videoId });
                    return;
                }

                try {
                    const note = await getVideoNote(videoId);
                    editor.setMarkdown(note.content || "");
                    toast.success("Note generated successfully");
                } catch (error) {
                    log.error("Failed to load note after generation", toError(error), { videoId });
                    toast.error("Failed to load generated note");
                }
            };

            loadNote();
        }
    }, [generatingNote, videoId]);

    const handleGenerateNote = useCallback(async () => {
        if (!videoId || generatingNote) return;

        const editor = noteEditorRef.current;
        if (!editor) {
            toast.error("Notes editor is not ready yet.");
            return;
        }

        const confirmed = await confirm({
            title: "Generate AI Note",
            message: "This will overwrite any existing notes you have written. Are you sure you want to continue?",
            confirmLabel: "Generate",
            cancelLabel: "Cancel",
            variant: "warning",
        });

        if (!confirmed) return;

        try {
            setGeneratingNote(true);
            didTriggerGenerationRef.current = true;

            const start = await generateVideoNote({ contentId: videoId, language: targetLanguage, contextMode: noteSettings.contextMode, learnerProfile });

            // If already ready (cached result), load immediately
            if (start.status === "ready" || !start.taskId) {
                const note = await getVideoNote(videoId);
                editor.setMarkdown(note.content || "");
                setGeneratingNote(false);
                didTriggerGenerationRef.current = false;
                return;
            }

            // Task submitted - SSE will notify completion via useVideoPageState
            // which will set generatingNote to false, triggering the useEffect above
            log.info("Note generation task submitted", { videoId, taskId: start.taskId });
        } catch (error) {
            log.error("Failed to start note generation", toError(error), { videoId });
            toast.error("Failed to start note generation");
            setGeneratingNote(false);
            didTriggerGenerationRef.current = false;
        }
    }, [videoId, targetLanguage, learnerProfile, generatingNote, setGeneratingNote, confirm, noteSettings.contextMode]);

    return {
        noteEditorRef,
        handleNoteEditorReady,
        handleGenerateNote,
    };
}

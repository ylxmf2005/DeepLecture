"use client";

import { useState, useCallback } from "react";
import { ScrollText, RefreshCw, AlertCircle, Loader2, Pencil, Save, X, Sparkles } from "lucide-react";
import { getVideoCheatsheet, saveVideoCheatsheet, generateVideoCheatsheet } from "@/lib/api";
import { useLanguageSettings, useNoteSettings } from "@/stores/useGlobalSettingsStore";
import { MarkdownRenderer } from "@/components/editor/MarkdownRenderer";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";
import { useSSEGenerationRetry } from "@/hooks/useSSEGenerationRetry";

const log = logger.scope("CheatsheetTab");

interface CheatsheetTabProps {
    videoId: string;
    onSeek: (time: number) => void;
    refreshTrigger: number;
    onAddToNotes?: (markdown: string) => void;
}

interface CheatsheetData {
    content: string;
    updatedAt: string | null;
}

export function CheatsheetTab({ videoId, onSeek, refreshTrigger, onAddToNotes }: CheatsheetTabProps) {
    const { translated: language } = useLanguageSettings();
    const noteSettings = useNoteSettings();
    const [isEditing, setIsEditing] = useState(false);
    const [editContent, setEditContent] = useState("");
    const [isSaving, setIsSaving] = useState(false);

    const fetchContent = useCallback(async (): Promise<CheatsheetData | null> => {
        const result = await getVideoCheatsheet(videoId);
        if (result.content) {
            return { content: result.content, updatedAt: result.updatedAt };
        }
        return null;
    }, [videoId]);

    const submitGeneration = useCallback(async () => {
        return await generateVideoCheatsheet({
            contentId: videoId,
            language: language || "en",
            contextMode: noteSettings.contextMode,
            minCriticality: "medium",
            targetPages: 2,
            subjectType: "auto",
        });
    }, [videoId, language, noteSettings.contextMode]);

    const { data, loading, loadError, isGenerating, clearError, handleGenerate } =
        useSSEGenerationRetry<CheatsheetData>({
            contentId: videoId,
            refreshTrigger,
            fetchContent,
            submitGeneration,
            log,
            taskType: "cheatsheet_generation",
        });

    const content = data?.content ?? "";
    const updatedAt = data?.updatedAt ?? null;

    const handleEdit = useCallback(() => {
        setEditContent(content);
        setIsEditing(true);
    }, [content]);

    const handleCancelEdit = useCallback(() => {
        setIsEditing(false);
        setEditContent("");
    }, []);

    const handleSave = useCallback(async () => {
        setIsSaving(true);
        try {
            await saveVideoCheatsheet(videoId, editContent);
            setIsEditing(false);
            setEditContent("");
            log.info("Cheatsheet saved", { videoId });
        } catch (err) {
            log.error("Failed to save cheatsheet", toError(err));
        } finally {
            setIsSaving(false);
        }
    }, [videoId, editContent]);

    const handleAddToNotes = useCallback(() => {
        if (onAddToNotes && content) {
            onAddToNotes(content);
        }
    }, [onAddToNotes, content]);

    const hasContent = content.length > 0;
    const hasError = loadError !== null;

    // Loading state
    if (loading && !hasContent) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-6">
                <Loader2 className="w-8 h-8 text-amber-600 animate-spin" />
                <p className="text-sm text-muted-foreground">Loading cheatsheet...</p>
            </div>
        );
    }

    // Generating state
    if (isGenerating) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-6">
                <div className="relative">
                    <Loader2 className="w-12 h-12 text-amber-600 animate-spin" />
                </div>
                <div className="space-y-2">
                    <p className="text-foreground font-medium">Generating cheatsheet...</p>
                    <p className="text-sm text-muted-foreground max-w-xs">
                        Extracting key knowledge points and formatting for quick exam reference.
                    </p>
                </div>
            </div>
        );
    }

    // Error state
    if (hasError && !hasContent) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-4">
                <div className="bg-red-50 dark:bg-red-900/20 p-4 rounded-full">
                    <AlertCircle className="w-8 h-8 text-red-600 dark:text-red-400" />
                </div>
                <p className="text-foreground font-medium">Error</p>
                <p className="text-sm text-muted-foreground max-w-xs">{loadError}</p>
                <button
                    onClick={clearError}
                    className="text-sm text-amber-600 dark:text-amber-400 hover:underline"
                >
                    Dismiss
                </button>
            </div>
        );
    }

    // Idle state - no content yet
    if (!hasContent) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-6">
                <div className="bg-amber-50 dark:bg-amber-900/20 p-6 rounded-full">
                    <ScrollText className="w-12 h-12 text-amber-600 dark:text-amber-400" />
                </div>
                <div className="max-w-xs space-y-2">
                    <h3 className="text-lg font-semibold text-foreground">Exam Cheatsheet</h3>
                    <p className="text-sm text-muted-foreground">
                        Generate a high-density cheatsheet with key formulas, definitions, and facts for quick exam reference.
                    </p>
                </div>
                <button
                    onClick={handleGenerate}
                    disabled={isGenerating}
                    className="inline-flex items-center gap-2 px-6 py-2.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg font-medium transition-colors shadow-sm disabled:opacity-50"
                >
                    <Sparkles className="w-4 h-4" />
                    Generate Cheatsheet
                </button>
            </div>
        );
    }

    // Content view
    return (
        <div className="flex flex-col h-full bg-background">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-card">
                <div className="flex items-center gap-2">
                    <ScrollText className="w-5 h-5 text-amber-600 dark:text-amber-400" />
                    <h3 className="font-semibold text-foreground">Cheatsheet</h3>
                    {updatedAt && (
                        <span className="text-xs text-muted-foreground">
                            Updated {new Date(updatedAt).toLocaleDateString()}
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-1">
                    {!isEditing ? (
                        <>
                            <button
                                onClick={handleEdit}
                                className="p-2 hover:bg-muted rounded-full transition-colors"
                                title="Edit"
                            >
                                <Pencil className="w-4 h-4 text-muted-foreground" />
                            </button>
                            <button
                                onClick={handleGenerate}
                                disabled={isGenerating}
                                className="p-2 hover:bg-muted rounded-full transition-colors disabled:opacity-50"
                                title="Regenerate"
                            >
                                <RefreshCw className="w-4 h-4 text-muted-foreground" />
                            </button>
                        </>
                    ) : (
                        <>
                            <button
                                onClick={handleSave}
                                disabled={isSaving}
                                className="p-2 hover:bg-muted rounded-full transition-colors disabled:opacity-50"
                                title="Save"
                            >
                                {isSaving ? (
                                    <Loader2 className="w-4 h-4 text-muted-foreground animate-spin" />
                                ) : (
                                    <Save className="w-4 h-4 text-green-600" />
                                )}
                            </button>
                            <button
                                onClick={handleCancelEdit}
                                className="p-2 hover:bg-muted rounded-full transition-colors"
                                title="Cancel"
                            >
                                <X className="w-4 h-4 text-muted-foreground" />
                            </button>
                        </>
                    )}
                </div>
            </div>

            {/* Content area */}
            <div className="flex-1 overflow-y-auto p-4">
                {isEditing ? (
                    <textarea
                        value={editContent}
                        onChange={(e) => setEditContent(e.target.value)}
                        className="w-full h-full min-h-[400px] p-4 rounded-lg border border-border bg-background font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-amber-500"
                        placeholder="Enter cheatsheet content in Markdown..."
                    />
                ) : (
                    <div className="prose prose-sm dark:prose-invert max-w-none">
                        <MarkdownRenderer>{content}</MarkdownRenderer>
                    </div>
                )}
            </div>
        </div>
    );
}

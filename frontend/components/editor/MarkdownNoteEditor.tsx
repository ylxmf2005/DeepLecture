"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useTheme } from "next-themes";
import { Crepe } from "@milkdown/crepe";
import { replaceAll } from "@milkdown/kit/utils";
import { getVideoNote, saveVideoNote, uploadNoteImage } from "@/lib/api";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";

import "@milkdown/crepe/theme/common/style.css";
import "@milkdown/crepe/theme/frame.css";
import "katex/dist/katex.min.css";

const log = logger.scope("MarkdownNoteEditor");

// Extended Crepe type with setMarkdown helper
export interface CrepeEditor extends Crepe {
    setMarkdown: (markdown: string) => void;
}

interface MarkdownNoteEditorProps {
    videoId: string;
    initialContent?: string;
    onEditorReady?: (editor: CrepeEditor) => void;
}

export function MarkdownNoteEditor({ videoId, initialContent = "", onEditorReady }: MarkdownNoteEditorProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const editorRef = useRef<CrepeEditor | null>(null);
    const hasUserEditedRef = useRef(false);
    const saveTimeoutRef = useRef<number | null>(null);
    const [mounted, setMounted] = useState(false);
    const { resolvedTheme } = useTheme();

    // Hydration-safe mounting check - intentional pattern for SSR compatibility
    // eslint-disable-next-line react-hooks/set-state-in-effect
    useEffect(() => { setMounted(true); }, []);

    const scheduleServerSave = useCallback((markdown: string) => {
        if (saveTimeoutRef.current !== null) {
            window.clearTimeout(saveTimeoutRef.current);
        }
        saveTimeoutRef.current = window.setTimeout(() => {
            saveVideoNote(videoId, markdown).catch((error) => {
                log.error("Failed to save note to server", toError(error), { videoId });
            });
            saveTimeoutRef.current = null;
        }, 1000);
    }, [videoId]);

    const handleImageUpload = useCallback(async (file: File): Promise<string> => {
        try {
            const response = await uploadNoteImage(videoId, file);
            return `../notes_assets/${videoId}/${response.filename}`;
        } catch (error) {
            log.error("Failed to upload image", toError(error), { videoId });
            throw error;
        }
    }, [videoId]);

    useEffect(() => {
        if (!mounted || !containerRef.current) return;

        const crepe = new Crepe({
            root: containerRef.current,
            defaultValue: initialContent,
            features: {
                [Crepe.Feature.Cursor]: true,
                [Crepe.Feature.ListItem]: true,
                [Crepe.Feature.LinkTooltip]: true,
                [Crepe.Feature.ImageBlock]: true,
                [Crepe.Feature.BlockEdit]: true,
                [Crepe.Feature.Placeholder]: true,
                [Crepe.Feature.Toolbar]: true,
                [Crepe.Feature.CodeMirror]: true,
                [Crepe.Feature.Table]: true,
                [Crepe.Feature.Latex]: true,
            },
            featureConfigs: {
                [Crepe.Feature.Placeholder]: {
                    text: "Start writing your notes...",
                    mode: "block",
                },
                [Crepe.Feature.ImageBlock]: {
                    onUpload: handleImageUpload,
                },
            },
        });

        crepe.create().then(() => {
            // Add setMarkdown helper method
            const crepeWithHelper = crepe as CrepeEditor;
            crepeWithHelper.setMarkdown = (markdown: string) => {
                crepe.editor.action(replaceAll(markdown));
            };

            editorRef.current = crepeWithHelper;

            // Load from localStorage first
            const saved = localStorage.getItem(`note-${videoId}`);
            if (saved) {
                crepeWithHelper.setMarkdown(saved);
            }

            // Listen for changes
            crepe.on((api) => {
                api.markdownUpdated(() => {
                    hasUserEditedRef.current = true;
                    const markdown = crepe.getMarkdown();
                    localStorage.setItem(`note-${videoId}`, markdown);
                    scheduleServerSave(markdown);
                });
            });

            if (onEditorReady) {
                onEditorReady(crepeWithHelper);
            }
        });

        return () => {
            if (saveTimeoutRef.current !== null) {
                window.clearTimeout(saveTimeoutRef.current);
            }
            crepe.destroy();
        };
    }, [mounted, videoId, initialContent, handleImageUpload, scheduleServerSave, onEditorReady]);

    // Load note from server
    useEffect(() => {
        if (!mounted) return;

        let cancelled = false;

        (async () => {
            try {
                const response = await getVideoNote(videoId);
                if (cancelled) return;

                const content = response.content ?? "";
                // Do not clobber local draft if user has already edited locally.
                // If there's no local content yet, treat server as initial source of truth.
                const storageKey = `note-${videoId}`;
                const localDraft = localStorage.getItem(storageKey);
                const hasLocal = typeof localDraft === "string" && localDraft.trim().length > 0;
                if (!hasUserEditedRef.current && !hasLocal) {
                    localStorage.setItem(storageKey, content);
                }

                if (content && editorRef.current && !hasUserEditedRef.current) {
                    editorRef.current.setMarkdown(content);
                }
            } catch (error) {
                log.error("Failed to load server note", toError(error), { videoId });
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [mounted, videoId]);

    // Handle theme changes
    useEffect(() => {
        if (!containerRef.current) return;
        const isDark = resolvedTheme === "dark";
        containerRef.current.classList.toggle("dark", isDark);
    }, [resolvedTheme]);

    if (!mounted) {
        return (
            <div className="flex flex-col h-full">
                <div className="flex-1 border-0 overflow-hidden min-h-0 bg-background flex items-center justify-center">
                    <p className="text-muted-foreground text-sm">Loading editor...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full">
            <div
                ref={containerRef}
                className="flex-1 border-0 overflow-hidden min-h-0 bg-background"
            />
            <style jsx global>{`
                .milkdown {
                    height: 100%;
                    overflow: auto;
                }
                .milkdown .editor {
                    padding: 1rem;
                    min-height: 100%;
                }
                .milkdown .ProseMirror {
                    outline: none;
                }
                .milkdown .ProseMirror:focus {
                    outline: none;
                }
                /* Dark mode adjustments - deep blue/gray palette */
                .dark .milkdown {
                    --crepe-color-background: hsl(var(--background));
                    --crepe-color-on-background: hsl(var(--foreground));
                    --crepe-color-surface: hsl(var(--background));
                    --crepe-color-surface-low: hsl(var(--muted));
                    --crepe-color-on-surface: hsl(var(--foreground));
                    --crepe-color-on-surface-variant: hsl(var(--muted-foreground));
                    --crepe-color-outline: hsl(var(--border));
                    --crepe-color-primary: hsl(var(--primary));
                    --crepe-color-secondary: hsl(var(--secondary));
                    --crepe-color-on-secondary: hsl(var(--secondary-foreground));
                    --crepe-color-inverse: hsl(var(--foreground));
                    --crepe-color-on-inverse: hsl(var(--background));
                    --crepe-color-inline-code: hsl(var(--accent));
                    --crepe-color-error: hsl(var(--destructive));
                    --crepe-color-hover: hsl(var(--accent));
                    --crepe-color-selected: hsl(var(--accent));
                    --crepe-color-inline-area: hsl(var(--muted));
                }
            `}</style>
        </div>
    );
}

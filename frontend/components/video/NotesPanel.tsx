"use client";

import { useCallback, useState } from "react";
import { MarkdownNoteEditor, type CrepeEditor } from "@/components/MarkdownNoteEditor";
import { cn } from "@/lib/utils";
import { FileText, Save, Maximize2 } from "lucide-react";

type NoteTabType = "notes" | "flashcard" | "test" | "report" | "cheatsheet" | "podcast";

interface NotesPanelProps {
    videoId: string;
    onEditorReady: (editor: CrepeEditor) => void;
}

export function NotesPanel({ videoId, onEditorReady }: NotesPanelProps) {
    const [noteTab, setNoteTab] = useState<NoteTabType>("notes");

    const handleToggleFullscreen = useCallback(() => {
        const editor = document.querySelector('.markdown-note-editor-container');
        if (editor) {
            if (document.fullscreenElement) {
                document.exitFullscreen();
            } else {
                editor.requestFullscreen();
            }
        }
    }, []);

    const renderPlaceholderTab = (label: string) => (
        <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
                <FileText className="w-16 h-16 mx-auto mb-4 opacity-20" />
                <p className="text-sm">{label} feature coming soon...</p>
            </div>
        </div>
    );

    return (
        <div className="flex-1 min-h-0 flex flex-col bg-card dark:bg-[#20293a] rounded-xl border border-border shadow-sm overflow-hidden">
            <div className="flex border-b border-border px-2 gap-1 overflow-x-auto no-scrollbar items-center">
                {(["notes", "flashcard", "test", "report", "cheatsheet", "podcast"] as NoteTabType[]).map((tab) => (
                    <button
                        key={tab}
                        onClick={() => setNoteTab(tab)}
                        className={cn(
                            "px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap flex-shrink-0",
                            noteTab === tab
                                ? "border-blue-500 text-blue-600 dark:text-blue-400"
                                : "border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                        )}
                    >
                        {tab.charAt(0).toUpperCase() + tab.slice(1)}
                    </button>
                ))}

                <div className="flex-1" />

                {/* Auto-saved indicator and Fullscreen button - only show when Notes tab is active */}
                {noteTab === "notes" && (
                    <div className="flex items-center gap-3 pr-2">
                        <span className="text-xs text-muted-foreground flex items-center gap-1 whitespace-nowrap">
                            <Save className="w-3 h-3" />
                            Auto-saved
                        </span>
                        <button
                            onClick={handleToggleFullscreen}
                            className="p-1.5 hover:bg-muted rounded-md transition-colors"
                            title="Toggle fullscreen"
                        >
                            <Maximize2 className="w-4 h-4 text-muted-foreground" />
                        </button>
                    </div>
                )}
            </div>
            <div className="flex-1 min-h-0 relative markdown-note-editor-container">
                {noteTab === "notes" && (
                    <MarkdownNoteEditor
                        videoId={videoId}
                        onEditorReady={onEditorReady}
                    />
                )}
                {noteTab === "flashcard" && renderPlaceholderTab("Flashcard")}
                {noteTab === "test" && renderPlaceholderTab("Test")}
                {noteTab === "report" && renderPlaceholderTab("Report")}
                {noteTab === "cheatsheet" && renderPlaceholderTab("Cheatsheet")}
                {noteTab === "podcast" && renderPlaceholderTab("Podcast")}
            </div>
        </div>
    );
}

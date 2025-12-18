import { X, ArrowLeft, Play, Loader2, MessageSquare, FilePlus, Sparkles } from "lucide-react";
import { useEffect } from "react";
import { MarkdownRenderer } from "@/components/editor/MarkdownRenderer";

interface MissedContentDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onJumpBack: () => void;
    onGenerateSummary?: () => void;
    summary: string;
    missedDuration: string;
    isLoading: boolean;
    onAsk?: () => void;
    onAddToNotes?: () => void;
}

export function MissedContentDialog({
    isOpen,
    onClose,
    onJumpBack,
    onGenerateSummary,
    summary,
    missedDuration,
    isLoading,
    onAsk,
    onAddToNotes,
}: MissedContentDialogProps) {
    useEffect(() => {
        const handleEsc = (e: KeyboardEvent) => {
            if (e.key === "Escape") onClose();
        };
        if (isOpen) {
            window.addEventListener("keydown", handleEsc);
            document.body.style.overflow = "hidden";
        }
        return () => {
            window.removeEventListener("keydown", handleEsc);
            document.body.style.overflow = "unset";
        };
    }, [isOpen, onClose]);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
            <div
                className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-xl flex flex-col animate-in zoom-in-95 duration-200 border border-gray-200 dark:border-gray-800"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-800">
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                        Welcome Back
                    </h2>
                    <button
                        onClick={onClose}
                        className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <div className="p-6 space-y-4">
                    <div className="bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 p-4 rounded-lg text-sm">
                        You were away for <strong>{missedDuration}</strong> while the video was playing.
                        {" "}
                        {isLoading
                            ? "We are generating a summary of what you missed..."
                            : summary
                                ? "Here is a summary of what you missed:"
                                : "You can generate a summary of what you missed if you like."}
                    </div>

                    <div className="max-w-none text-sm max-h-[40vh] overflow-y-auto bg-gray-50 dark:bg-gray-900/50 p-4 rounded-lg border border-gray-100 dark:border-gray-800">
                        {isLoading ? (
                            <div className="flex items-center justify-center text-gray-500 gap-2">
                                <Loader2 className="w-4 h-4 animate-spin" />
                                <span>Summarizing the missed content...</span>
                            </div>
                        ) : summary ? (
                            <MarkdownRenderer>{summary}</MarkdownRenderer>
                        ) : (
                            <div className="text-gray-500 text-sm">
                                No summary has been generated yet. Click{" "}
                                <span className="font-medium">Generate Summary</span> below to get a summary of what
                                you missed.
                            </div>
                        )}
                    </div>

                    <div className="flex flex-col gap-3 pt-2">
                        {(onAsk || onAddToNotes) && (
                            <div className="flex items-center justify-between gap-2">
                                <div className="flex gap-2">
                                    {onAsk && (
                                        <button
                                            onClick={onAsk}
                                            disabled={isLoading || !summary}
                                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-blue-600 hover:bg-blue-50 disabled:opacity-50 disabled:hover:bg-transparent dark:text-blue-400 dark:hover:bg-blue-900/30"
                                            title="Ask AI about this missed segment"
                                        >
                                            <MessageSquare className="w-3.5 h-3.5" />
                                            Ask AI about this
                                        </button>
                                    )}
                                    {onAddToNotes && (
                                        <button
                                            onClick={onAddToNotes}
                                            disabled={isLoading || !summary}
                                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-emerald-600 hover:bg-emerald-50 disabled:opacity-50 disabled:hover:bg-transparent dark:text-emerald-400 dark:hover:bg-emerald-900/30"
                                            title="Add this summary to notes"
                                        >
                                            <FilePlus className="w-3.5 h-3.5" />
                                            Add to notes
                                        </button>
                                    )}
                                </div>
                            </div>
                        )}

                        <div className="flex flex-col sm:flex-row gap-3">
                            <button
                                onClick={onJumpBack}
                                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
                            >
                                <ArrowLeft className="w-4 h-4" />
                                Rewind to Where I Left
                            </button>
                            {onGenerateSummary && (
                                <button
                                    onClick={onGenerateSummary}
                                    disabled={isLoading}
                                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 disabled:hover:bg-emerald-600 text-white rounded-lg font-medium transition-colors"
                                >
                                    {isLoading ? (
                                        <>
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                            Generating Summary...
                                        </>
                                    ) : (
                                        <>
                                            <Sparkles className="w-4 h-4" />
                                            Generate Summary
                                        </>
                                    )}
                                </button>
                            )}
                            <button
                                onClick={onClose}
                                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg font-medium transition-colors"
                            >
                                <Play className="w-4 h-4" />
                                Continue Watching
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

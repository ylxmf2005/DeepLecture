import { X, FileText, Globe, Volume2, Loader2, Sparkles, MessageSquare, Video, Trash2, Pencil, Check } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ContentItem, SubtitleSource, VoiceoverEntry } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ProcessingAction } from "@/hooks/useVideoPageState";
import { useFocusTrap } from "@/hooks/useFocusTrap";

/** Format duration in seconds to mm:ss or hh:mm:ss */
function formatDuration(seconds: number): string {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) {
        return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
    }
    return `${m}:${s.toString().padStart(2, "0")}`;
}

export interface ActionsDialogProps {
    isOpen: boolean;
    onClose: () => void;
    video: ContentItem;
    // Subtitle actions
    processing: boolean;
    processingAction: ProcessingAction;
    handleGenerateSubtitles: () => void;
    handleTranslateSubtitles: () => void;
    // Voiceover actions
    voiceoverName: string;
    setVoiceoverName: (name: string) => void;
    voiceoverProcessing: SubtitleSource | null;
    handleGenerateVoiceover: (source: SubtitleSource) => void;
    selectedVoiceoverId: string | null;
    setSelectedVoiceoverId: (id: string | null) => void;
    voiceovers: VoiceoverEntry[];
    voiceoversLoading: boolean;
    handleDeleteVoiceover: (voiceoverId: string) => void;
    handleUpdateVoiceover: (voiceoverId: string, name: string) => Promise<void>;
    // Timeline
    timelineLoading: boolean;
    hasTimeline: boolean;
    handleGenerateTimeline: () => void;
    // Slide lecture generation
    generatingVideo?: boolean;
    handleGenerateSlideLecture?: (force: boolean) => void;
    // Note generation
    handleGenerateNote: () => void;
    generatingNote: boolean;
}

export function ActionsDialog({
    isOpen,
    onClose,
    video,
    processing,
    processingAction,
    handleGenerateSubtitles,
    handleTranslateSubtitles,
    voiceoverName,
    setVoiceoverName,
    voiceoverProcessing,
    handleGenerateVoiceover,
    selectedVoiceoverId,
    setSelectedVoiceoverId,
    voiceovers,
    voiceoversLoading,
    handleDeleteVoiceover,
    handleUpdateVoiceover,
    timelineLoading,
    hasTimeline,
    handleGenerateTimeline,
    generatingVideo,
    handleGenerateSlideLecture,
    handleGenerateNote,
    generatingNote,
}: ActionsDialogProps) {
    const hasSubtitles = video?.subtitleStatus === "ready";
    const isSlideMode = video?.type === "slide";

    // Inline edit state
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editingName, setEditingName] = useState("");

    const handleStartEdit = (e: React.MouseEvent, vo: VoiceoverEntry) => {
        e.preventDefault();
        e.stopPropagation();
        setEditingId(vo.id);
        setEditingName(vo.name);
    };

    const handleCancelEdit = (e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setEditingId(null);
        setEditingName("");
    };

    const handleSaveEdit = async (e: React.MouseEvent | React.KeyboardEvent, id: string) => {
        e.preventDefault();
        e.stopPropagation();
        const trimmed = editingName.trim();
        if (!trimmed || trimmed === id) {
            setEditingId(null);
            return;
        }
        await handleUpdateVoiceover(id, trimmed);
        setEditingId(null);
    };

    // Dialog container ref for focus trap
    const dialogRef = useRef<HTMLDivElement>(null);
    const dialogA11yProps = useFocusTrap({
        isOpen,
        onClose,
        containerRef: dialogRef,
    });

    // Lock body scroll when open
    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = "hidden";
        }
        return () => {
            document.body.style.overflow = "unset";
        };
    }, [isOpen]);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
            <div
                ref={dialogRef}
                {...dialogA11yProps}
                aria-labelledby="actions-dialog-title"
                className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col animate-in zoom-in-95 duration-200"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-800">
                    <h2 id="actions-dialog-title" className="text-lg font-semibold text-gray-900 dark:text-gray-100">Actions</h2>
                    <button
                        onClick={onClose}
                        aria-label="Close actions dialog"
                        className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-6 space-y-8 bg-gray-50/50 dark:bg-gray-900/50">
                    {/* Generate Video Section - For slide mode */}
                    {isSlideMode && handleGenerateSlideLecture && (
                        <section className="space-y-4">
                            <div className="flex items-center gap-2 text-indigo-600 dark:text-indigo-400">
                                <Video className="w-5 h-5" />
                                <h3 className="font-semibold text-gray-900 dark:text-gray-100">Video Generation</h3>
                            </div>

                            <div className="grid grid-cols-1 gap-3">
                                <button
                                    onClick={() => handleGenerateSlideLecture(true)}
                                    disabled={generatingVideo}
                                    className="group relative flex items-center justify-between p-4 rounded-xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:border-indigo-500 dark:hover:border-indigo-500 hover:shadow-md transition-all text-left overflow-hidden disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    <div className="flex items-center gap-3 z-10">
                                        <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 group-hover:scale-110 transition-transform">
                                            <Video className="w-5 h-5" />
                                        </div>
                                        <div className="flex flex-col">
                                            <span className="font-medium text-gray-900 dark:text-gray-100">
                                                {video?.videoStatus === "ready" ? "Regenerate Video" : "Generate Video"}
                                            </span>
                                            <span className="text-xs text-gray-500 dark:text-gray-400">
                                                {video?.videoStatus === "ready" ? "Regenerate lecture video from slide deck" : "Create lecture video from slide deck"}
                                            </span>
                                        </div>
                                    </div>
                                    {generatingVideo && (
                                        <Loader2 className="w-5 h-5 animate-spin text-indigo-500" />
                                    )}
                                </button>
                            </div>
                        </section>
                    )}

                    {/* Subtitle Actions Section - Hidden for slide mode */}
                    {!isSlideMode && (
                        <section className="space-y-4">
                            <div className="flex items-center gap-2 text-indigo-600 dark:text-indigo-400">
                                <FileText className="w-5 h-5" />
                                <h3 className="font-semibold text-gray-900 dark:text-gray-100">Subtitle Management</h3>
                            </div>

                            <div className="grid grid-cols-1 gap-3">
                                <button
                                    onClick={handleGenerateSubtitles}
                                    disabled={processing}
                                    className="group relative flex items-center justify-between p-4 rounded-xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:border-indigo-500 dark:hover:border-indigo-500 hover:shadow-md transition-all text-left overflow-hidden"
                                >
                                    <div className="flex items-center gap-3 z-10">
                                        <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 group-hover:scale-110 transition-transform">
                                            <FileText className="w-5 h-5" />
                                        </div>
                                        <div className="flex flex-col">
                                            <span className="font-medium text-gray-900 dark:text-gray-100">
                                                {hasSubtitles ? "Regenerate Subtitles" : "Generate Subtitles"}
                                            </span>
                                            <span className="text-xs text-gray-500 dark:text-gray-400">
                                                {hasSubtitles ? "Re-extract subtitles from video audio" : "Extract subtitles from video audio"}
                                            </span>
                                        </div>
                                    </div>
                                    {processing && processingAction === "generate" && (
                                        <Loader2 className="w-5 h-5 animate-spin text-indigo-500" />
                                    )}
                                </button>

                                <button
                                    onClick={handleTranslateSubtitles}
                                    disabled={processing || !hasSubtitles}
                                    className="group relative flex items-center justify-between p-4 rounded-xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:border-indigo-500 dark:hover:border-indigo-500 hover:shadow-md transition-all text-left disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:border-gray-200 disabled:hover:shadow-none"
                                >
                                    <div className="flex items-center gap-3 z-10">
                                        <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 group-hover:scale-110 transition-transform">
                                            <Sparkles className="w-5 h-5" />
                                        </div>
                                        <div className="flex flex-col">
                                            <span className="font-medium text-gray-900 dark:text-gray-100">
                                                {video.translationStatus === "ready" ? "Re-enhance & Translate" : "Enhance & Translate"}
                                            </span>
                                            <span className="text-xs text-gray-500 dark:text-gray-400">
                                                {video.translationStatus === "ready" ? "Regenerate enhanced bilingual subtitles" : "Fix ASR errors & generate bilingual subtitles"}
                                            </span>
                                        </div>
                                    </div>
                                    {processing && processingAction === "translate" && (
                                        <Loader2 className="w-5 h-5 animate-spin text-indigo-500" />
                                    )}
                                </button>
                            </div>
                        </section>
                    )}

                    {/* AI Notes Section */}
                    <section className="space-y-4">
                        <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
                            <FileText className="w-5 h-5" />
                            <h3 className="font-semibold text-gray-900 dark:text-gray-100">AI Notes</h3>
                        </div>

                        <div className="grid grid-cols-1 gap-3">
                            <button
                                type="button"
                                onClick={handleGenerateNote}
                                disabled={generatingNote}
                                className="group relative flex items-center justify-between p-4 rounded-xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:border-emerald-500 dark:hover:border-emerald-500 hover:shadow-md transition-all text-left overflow-hidden disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                <div className="flex items-center gap-3 z-10">
                                    <div className="p-2 rounded-lg bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400 group-hover:scale-110 transition-transform">
                                        <Sparkles className="w-5 h-5" />
                                    </div>
                                    <div className="flex flex-col">
                                        <span className="font-medium text-gray-900 dark:text-gray-100">
                                            Generate Note
                                        </span>
                                        <span className="text-xs text-gray-500 dark:text-gray-400">
                                            Use AI to generate a full lecture note in Markdown.
                                        </span>
                                    </div>
                                </div>
                                {generatingNote && (
                                    <Loader2 className="w-5 h-5 animate-spin text-emerald-500" />
                                )}
                            </button>
                        </div>
                    </section>

                    {/* Voiceover Actions Section - Hidden for slide mode */}
                    {!isSlideMode && (
                        <section className="space-y-4">
                            <div className="flex items-center gap-2 text-purple-600 dark:text-purple-400">
                                <Volume2 className="w-5 h-5" />
                                <h3 className="font-semibold text-gray-900 dark:text-gray-100">AI Voiceover</h3>
                            </div>

                            <div className="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-5">
                                <div className="space-y-2">
                                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">New Voiceover</label>
                                    <div className="flex gap-2">
                                        <input
                                            type="text"
                                            value={voiceoverName}
                                            onChange={(e) => setVoiceoverName(e.target.value)}
                                            placeholder="Name (e.g. Edge TTS Chinese)"
                                            className="flex-1 px-4 py-2 rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 transition-all"
                                        />
                                    </div>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-2">
                                        <button
                                            onClick={() => handleGenerateVoiceover("original")}
                                            disabled={voiceoverProcessing !== null || video.subtitleStatus !== "ready" || !voiceoverName.trim()}
                                            className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-300 text-xs font-medium hover:bg-purple-100 dark:hover:bg-purple-900/40 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                        >
                                            {voiceoverProcessing === "original" ? <Loader2 className="w-3 h-3 animate-spin" /> : <Volume2 className="w-3 h-3" />}
                                            From Original
                                        </button>
                                        <button
                                            onClick={() => handleGenerateVoiceover("translated")}
                                            disabled={voiceoverProcessing !== null || video.translationStatus !== "ready" || !voiceoverName.trim()}
                                            className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-300 text-xs font-medium hover:bg-purple-100 dark:hover:bg-purple-900/40 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                        >
                                            {voiceoverProcessing === "translated" ? <Loader2 className="w-3 h-3 animate-spin" /> : <Globe className="w-3 h-3" />}
                                            From Translated
                                        </button>
                                    </div>
                                </div>

                                <div className="space-y-3 pt-2 border-t border-gray-100 dark:border-gray-700">
                                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Select Audio Track</label>
                                    <div className="space-y-2 max-h-48 overflow-y-auto pr-1 custom-scrollbar">
                                        <label className={cn(
                                            "flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all",
                                            selectedVoiceoverId === null
                                                ? "bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-800 ring-1 ring-purple-500/20"
                                                : "bg-gray-50 dark:bg-gray-900 border-transparent hover:bg-gray-100 dark:hover:bg-gray-800"
                                        )}>
                                            <input
                                                type="radio"
                                                name="voiceover-selection"
                                                value="original"
                                                checked={selectedVoiceoverId === null}
                                                onChange={() => setSelectedVoiceoverId(null)}
                                                className="text-purple-600 focus:ring-purple-500"
                                            />
                                            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Original Audio</span>
                                        </label>

                                        {voiceoversLoading && (
                                            <div className="flex items-center justify-center py-4 text-gray-400">
                                                <Loader2 className="w-4 h-4 animate-spin mr-2" />
                                                <span className="text-xs">Loading tracks...</span>
                                            </div>
                                        )}

                                        {voiceovers.map((vo) => (
                                            <label
                                                key={vo.id}
                                                className={cn(
                                                    "flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all",
                                                    selectedVoiceoverId === vo.id && vo.status === "done"
                                                        ? "bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-800 ring-1 ring-purple-500/20"
                                                        : "bg-gray-50 dark:bg-gray-900 border-transparent hover:bg-gray-100 dark:hover:bg-gray-800"
                                                )}
                                            >
                                                <input
                                                    type="radio"
                                                    name="voiceover-selection"
                                                    value={vo.id}
                                                    checked={selectedVoiceoverId === vo.id && vo.status === "done"}
                                                    onChange={() => vo.status === "done" && setSelectedVoiceoverId(vo.id)}
                                                    disabled={vo.status !== "done"}
                                                    className="text-purple-600 focus:ring-purple-500 disabled:opacity-50 disabled:cursor-not-allowed"
                                                />
                                                <div className="flex flex-col flex-1 min-w-0">
                                                    {editingId === vo.id ? (
                                                        <div
                                                            className="flex items-center gap-2 mb-1"
                                                            onClick={(e) => { e.preventDefault(); e.stopPropagation(); }}
                                                        >
                                                            <input
                                                                type="text"
                                                                value={editingName}
                                                                onChange={(e) => setEditingName(e.target.value)}
                                                                className="flex-1 h-7 text-sm px-2 rounded border border-purple-200 dark:border-purple-700 bg-white dark:bg-gray-950 focus:outline-none focus:ring-2 focus:ring-purple-500/20"
                                                                autoFocus
                                                                onKeyDown={(e) => {
                                                                    if (e.key === "Enter") handleSaveEdit(e, vo.id);
                                                                    if (e.key === "Escape") handleCancelEdit(e as unknown as React.MouseEvent);
                                                                }}
                                                            />
                                                            <button
                                                                onClick={(e) => handleSaveEdit(e, vo.id)}
                                                                className="p-1 rounded hover:bg-green-100 dark:hover:bg-green-900/30 text-green-600 transition-colors"
                                                                title="Save"
                                                            >
                                                                <Check className="w-4 h-4" />
                                                            </button>
                                                            <button
                                                                onClick={handleCancelEdit}
                                                                className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 transition-colors"
                                                                title="Cancel"
                                                            >
                                                                <X className="w-4 h-4" />
                                                            </button>
                                                        </div>
                                                    ) : (
                                                        <span className="text-sm font-medium text-gray-700 dark:text-gray-300 truncate">
                                                            {vo.name}
                                                        </span>
                                                    )}
                                                    <span className="text-[10px] text-gray-400 flex items-center gap-2">
                                                        {vo.language} · {vo.subtitleSource} · {new Date(vo.createdAt).toLocaleDateString()}
                                                        {vo.duration != null && vo.status === "done" && (
                                                            <span>· {formatDuration(vo.duration)}</span>
                                                        )}
                                                        {vo.status === "processing" && (
                                                            <span className="inline-flex items-center gap-1 text-amber-500">
                                                                <Loader2 className="w-3 h-3 animate-spin" /> processing
                                                            </span>
                                                        )}
                                                        {vo.status === "error" && (
                                                            <span className="inline-flex items-center gap-1 text-red-500">
                                                                • error
                                                            </span>
                                                        )}
                                                    </span>
                                                    {vo.error && (
                                                        <span className="text-[10px] text-red-500 line-clamp-2">{vo.error}</span>
                                                    )}
                                                </div>
                                                <div className="flex items-center gap-1">
                                                    {vo.status === "done" && editingId !== vo.id && (
                                                        <button
                                                            type="button"
                                                            onClick={(e) => handleStartEdit(e, vo)}
                                                            className="p-1.5 rounded-md text-gray-400 hover:text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-900/20 transition-colors"
                                                            title="Edit name"
                                                        >
                                                            <Pencil className="w-3.5 h-3.5" />
                                                        </button>
                                                    )}
                                                    <button
                                                        type="button"
                                                        onClick={(e) => {
                                                            e.preventDefault();
                                                            e.stopPropagation();
                                                            if (confirm(`Delete voiceover "${vo.name}"?`)) {
                                                                handleDeleteVoiceover(vo.id);
                                                            }
                                                        }}
                                                        className="p-1.5 rounded-md text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                                                        title="Delete voiceover"
                                                    >
                                                        <Trash2 className="w-3.5 h-3.5" />
                                                    </button>
                                                </div>
                                            </label>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        </section>
                    )}

                    {/* Timeline Section */}
                    <section className="space-y-4">
                        <div className="flex items-center gap-2 text-teal-600 dark:text-teal-400">
                            <MessageSquare className="w-5 h-5" />
                            <h3 className="font-semibold text-gray-900 dark:text-gray-100">Timeline</h3>
                        </div>

                        <div className="grid grid-cols-1 gap-3">
                            <button
                                onClick={handleGenerateTimeline}
                                disabled={timelineLoading || video.subtitleStatus !== "ready"}
                                className="group relative flex items-center justify-between p-4 rounded-xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:border-teal-500 dark:hover:border-teal-500 hover:shadow-md transition-all text-left disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                <div className="flex items-center gap-3 z-10">
                                    <div className="p-2 rounded-lg bg-teal-50 dark:bg-teal-900/30 text-teal-600 dark:text-teal-400 group-hover:scale-110 transition-transform">
                                        <MessageSquare className="w-5 h-5" />
                                    </div>
                                    <div className="flex flex-col">
                                        <span className="font-medium text-gray-900 dark:text-gray-100">
                                            {hasTimeline ? "Regenerate Timeline" : "Generate Timeline"}
                                        </span>
                                        <span className="text-xs text-gray-500 dark:text-gray-400">
                                            {hasTimeline ? "Refresh AI-powered key moments" : "Create AI-powered timeline of key moments"}
                                        </span>
                                    </div>
                                </div>
                                {timelineLoading && <Loader2 className="w-5 h-5 animate-spin text-teal-500" />}
                            </button>
                        </div>
                    </section>
                </div>
            </div>
        </div>
    );
}

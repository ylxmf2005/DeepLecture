"use client";

import { useEffect, useState, memo } from "react";
import { formatTime } from "@/lib/timeFormat";
import { ExplanationData, getExplanationHistory, deleteExplanation, API_BASE_URL } from "@/lib/api";
import { Loader2, Clock, ChevronDown, ChevronUp, Trash2, MessageSquare, FilePlus } from "lucide-react";
import { MarkdownRenderer } from "@/components/editor/MarkdownRenderer";
import { cn } from "@/lib/utils";
import type { AskContextItem } from "@/lib/askTypes";
import { useConfirmDialog } from "@/contexts/ConfirmDialogContext";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";
import { useTaskNotification } from "@/hooks/useTaskNotification";

const log = logger.scope("ExplanationList");

interface ExplanationListProps {
    videoId: string;
    refreshTrigger: number;
    onSeek: (time: number) => void;
    onAddToAsk: (item: AskContextItem) => void;
    onAddToNotes?: (markdown: string) => void;
}

function ExplanationListBase({
    videoId,
    refreshTrigger,
    onSeek,
    onAddToAsk,
    onAddToNotes,
}: ExplanationListProps) {
    const [history, setHistory] = useState<ExplanationData[]>([]);
    const [loading, setLoading] = useState(true);
    const [expandedItems, setExpandedItems] = useState<Set<number>>(new Set());
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const { confirm } = useConfirmDialog();
    const { notifyOperation } = useTaskNotification();

    useEffect(() => {
        let cancelled = false;

        const fetchHistory = async () => {
            try {
                setLoading(true);
                const data = await getExplanationHistory(videoId);
                if (cancelled) return;
                setHistory(data.history);
            } catch (error) {
                log.error("Failed to load explanation history", toError(error), { videoId });
                notifyOperation("explanation_load", "error", toError(error).message);
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        };

        if (videoId) {
            fetchHistory();
        }

        return () => {
            cancelled = true;
        };
    }, [videoId, refreshTrigger, notifyOperation]);

    const toggleExpand = (index: number) => {
        setExpandedItems((prev) => {
            const newSet = new Set(prev);
            if (newSet.has(index)) {
                newSet.delete(index);
            } else {
                newSet.add(index);
            }
            return newSet;
        });
    };

    const handleDelete = async (item: ExplanationData) => {
        const derivedId = item.id ?? String(Math.round(item.timestamp * 1000));

        const confirmed = await confirm({
            title: "Delete Screenshot",
            message: "Are you sure you want to delete this screenshot? This action cannot be undone.",
            confirmLabel: "Delete",
            cancelLabel: "Cancel",
            variant: "danger",
        });

        if (!confirmed) return;

        try {
            setDeletingId(derivedId);
            await deleteExplanation(videoId, derivedId);
            setHistory((prev) =>
                prev.filter((entry) => (entry.id ?? String(Math.round(entry.timestamp * 1000))) !== derivedId)
            );
            notifyOperation("explanation_delete", "success");
        } catch (error) {
            log.error("Failed to delete explanation", toError(error), { videoId, explanationId: derivedId });
            notifyOperation("explanation_delete", "error", toError(error).message);
        } finally {
            setDeletingId(null);
        }
    };

    if (loading && history.length === 0) {
        return (
            <div className="flex justify-center py-12">
                <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
            </div>
        );
    }

    if (history.length === 0) {
        return (
            <div className="text-center py-12 text-gray-500 text-sm">
                No explanations yet. Capture a slide to generate one.
            </div>
        );
    }

    return (
        <div className="space-y-6 p-4 h-full overflow-y-auto">
            {history.map((item, index) => {
                const derivedId = item.id ?? String(Math.round(item.timestamp * 1000));
                const isExpanded = expandedItems.has(index);
                const isPending = !item.explanation;
                const isDeleting = deletingId === derivedId;

                return (
                    <div
                        key={derivedId ?? index}
                        className="bg-card dark:bg-card border border-border rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-shadow"
                    >
                        <div
                            className="relative aspect-video cursor-pointer group"
                            onClick={() => onSeek(item.timestamp)}
                        >
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                                src={item.imageUrl ? `${API_BASE_URL}${item.imageUrl}` : ""}
                                alt={`Slide at ${item.timestamp}s`}
                                className="w-full h-full object-cover"
                            />
                            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                                <div className="opacity-0 group-hover:opacity-100 bg-black/70 text-white text-xs px-2 py-1 rounded-full flex items-center gap-1">
                                    <Clock className="w-3 h-3" />
                                    {formatTime(item.timestamp)}
                                </div>
                            </div>

                            <div className="absolute top-2 right-2 flex gap-2">
                                <button
                                    type="button"
                                    onClick={(event) => {
                                        event.stopPropagation();
                                        onAddToAsk({
                                            type: 'screenshot',
                                            id: `screenshot-${derivedId}`,
                                            imageUrl: item.imageUrl ?? "",
                                            timestamp: item.timestamp,
                                            imagePath: item.imagePath,
                                        });
                                    }}
                                    className="inline-flex items-center justify-center rounded-full bg-black/60 text-white p-1 hover:bg-blue-600 transition-colors opacity-0 group-hover:opacity-100"
                                    title="Ask AI about this"
                                >
                                    <MessageSquare className="w-4 h-4" />
                                </button>

                                {onAddToNotes && (
                                    <button
                                        type="button"
                                        onClick={(event) => {
                                            event.stopPropagation();
                                            const timeLabel = formatTime(item.timestamp);
                                            const heading = `### Slide at ${timeLabel}`;
                                            const seg = (item.imagePath ?? "").split(/[\\/]/);
                                            const name = seg[seg.length - 1] ?? "";
                                            const relPath = name ? `../notes_assets/${videoId}/${name}` : "";
                                            const imageMarkdown = relPath
                                                ? `![Slide at ${timeLabel}](${relPath})`
                                                : "";
                                            const explanationMarkdown = item.explanation ? item.explanation : "";
                                            const blocks = [heading, imageMarkdown, explanationMarkdown].filter(Boolean);
                                            const snippet = blocks.join("\n\n");
                                            onAddToNotes(snippet);
                                        }}
                                        className="inline-flex items-center justify-center rounded-full bg-black/60 text-white p-1 hover:bg-emerald-600 transition-colors opacity-0 group-hover:opacity-100"
                                        title="Add to notes"
                                    >
                                        <FilePlus className="w-4 h-4" />
                                    </button>
                                )}

                                <button
                                    type="button"
                                    onClick={(event) => {
                                        event.stopPropagation();
                                        handleDelete(item);
                                    }}
                                    className="inline-flex items-center justify-center rounded-full bg-black/60 text-white p-1 hover:bg-red-600 transition-colors opacity-0 group-hover:opacity-100"
                                    disabled={isDeleting}
                                    aria-label="Delete screenshot"
                                >
                                    {isDeleting ? (
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                    ) : (
                                        <Trash2 className="w-4 h-4" />
                                    )}
                                </button>
                            </div>
                        </div>

                        <button
                            onClick={() => toggleExpand(index)}
                            className="w-full px-4 py-3 flex items-center justify-between hover:bg-muted/50 transition-colors border-t border-border"
                        >
                            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                                {isPending
                                    ? "Generating explanation..."
                                    : isExpanded
                                        ? "Hide Explanation"
                                        : "Show Explanation"}
                            </span>
                            {isExpanded ? (
                                <ChevronUp className="w-4 h-4 text-gray-500" />
                            ) : (
                                <ChevronDown className="w-4 h-4 text-gray-500" />
                            )}
                        </button>

                        <div className={cn(
                            "grid transition-all duration-300 ease-in-out",
                            isExpanded ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
                        )}>
                            <div className="overflow-hidden">
                                <div className="p-4 border-t border-border">
                                    {isPending ? (
                                        <div className="flex items-center gap-2 text-sm text-gray-500">
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                            <span>The explanation is being generated, please wait…</span>
                                        </div>
                                    ) : (
                                        <MarkdownRenderer onSeek={onSeek}>{item.explanation ?? ""}</MarkdownRenderer>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

export const ExplanationList = memo(ExplanationListBase, (prevProps, nextProps) => {
    return (
        prevProps.videoId === nextProps.videoId &&
        prevProps.refreshTrigger === nextProps.refreshTrigger &&
        (prevProps.onAddToNotes === undefined) === (nextProps.onAddToNotes === undefined)
    );
});

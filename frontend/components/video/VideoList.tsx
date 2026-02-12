"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { Play, FileText, Globe, Clock, Loader2, FileVideo, Trash2, Edit2, Youtube, MonitorPlay } from "lucide-react";
import { listContent, ContentItem, deleteContent, renameContent } from "@/lib/api";
import { useConfirmDialog } from "@/contexts/ConfirmDialogContext";

const RenameDialog = dynamic(
    () => import("@/components/dialogs/RenameDialog").then((mod) => mod.RenameDialog),
    { ssr: false }
);
import { useTaskNotification } from "@/hooks/useTaskNotification";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";

const log = logger.scope("VideoList");

interface VideoListProps {
    refreshTrigger: number;
}

export function VideoList({ refreshTrigger }: VideoListProps) {
    const [items, setItems] = useState<ContentItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [deletingId, setDeletingId] = useState<string | null>(null);

    // Rename state
    const [renameItem, setRenameItem] = useState<ContentItem | null>(null);

    const { confirm } = useConfirmDialog();
    const { notifyOperation } = useTaskNotification();

    useEffect(() => {
        const fetchContent = async () => {
            try {
                setLoading(true);
                const data = await listContent();
                setItems(data.content);  // Unified API returns content array
                setError(null);
            } catch (err) {
                log.error("Failed to load content", toError(err));
                setError("Failed to load content.");
            } finally {
                setLoading(false);
            }
        };

        fetchContent();
    }, [refreshTrigger]);

    const handleDelete = async (contentId: string, event: React.MouseEvent) => {
        event.preventDefault();
        event.stopPropagation();

        const confirmed = await confirm({
            title: "Delete Content",
            message: "Are you sure you want to delete this content? This action cannot be undone.",
            confirmLabel: "Delete",
            cancelLabel: "Cancel",
            variant: "danger",
        });

        if (!confirmed) return;

        try {
            setDeletingId(contentId);
            await deleteContent(contentId);
            setItems(prevItems => prevItems.filter(item => item.id !== contentId));
            notifyOperation("content_delete", "success");
        } catch (err) {
            log.error("Failed to delete content", toError(err), { contentId });
            setError("Failed to delete content.");
            notifyOperation("content_delete", "error", toError(err).message);
        } finally {
            setDeletingId(null);
        }
    };

    const openRenameDialog = (item: ContentItem, event: React.MouseEvent) => {
        event.preventDefault();
        event.stopPropagation();
        setRenameItem(item);
    };

    const handleRename = async (newName: string) => {
        if (!renameItem) return;

        try {
            const result = await renameContent(renameItem.id, newName);
            setItems(prevItems => prevItems.map(item =>
                item.id === renameItem.id ? { ...item, filename: result.filename } : item
            ));
            setRenameItem(null);
            notifyOperation("content_rename", "success");
        } catch (err) {
            log.error("Failed to rename content", toError(err), { contentId: renameItem.id, newName });
            notifyOperation("content_rename", "error", toError(err).message);
        }
    };

    const getSourceIcon = (type: string, sourceType?: string) => {
        if (type === "slide") return FileVideo;
        if (sourceType === "youtube") return Youtube;
        if (sourceType === "bilibili") return MonitorPlay;
        if (sourceType === "remote") return Globe;
        return Play;
    };

    const getSourceLabel = (type: string, sourceType?: string) => {
        if (type === "slide") return "Slide Deck";
        if (sourceType === "youtube") return "YouTube";
        if (sourceType === "bilibili") return "Bilibili";
        if (sourceType === "remote") return "Remote";
        return "Local";
    };

    if (loading && items.length === 0) {
        return (
            <div className="flex justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="text-center py-12 text-red-500">
                {error}
            </div>
        );
    }

    if (items.length === 0) {
        return (
            <div className="text-center py-12 text-muted-foreground">
                No content uploaded yet.
            </div>
        );
    }

    return (
        <>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {items.map((item) => {
                    const isSlide = item.type === "slide";
                    const Icon = getSourceIcon(item.type, item.sourceType);

                    // Determine colors based on source
                    let iconBg = "bg-blue-50 dark:bg-blue-900/20";
                    let iconColor = "text-blue-600 dark:text-blue-400";

                    if (isSlide) {
                        iconBg = "bg-purple-50 dark:bg-purple-900/20";
                        iconColor = "text-purple-600 dark:text-purple-400";
                    } else if (item.sourceType === "youtube") {
                        iconBg = "bg-red-50 dark:bg-red-900/20";
                        iconColor = "text-red-600 dark:text-red-400";
                    } else if (item.sourceType === "bilibili") {
                        iconBg = "bg-pink-50 dark:bg-pink-900/20";
                        iconColor = "text-pink-600 dark:text-pink-400";
                    }

                    const isDeleting = deletingId === item.id;

                    return (
                        <div key={item.id} className="relative group h-full">
                            <Link
                                href={`/video/${item.id}`}
                                className="flex flex-col h-full p-5 bg-card rounded-xl border border-border hover:border-primary/50 transition-all shadow-sm hover:shadow-md hover:-translate-y-0.5"
                            >
                                <div className="flex items-start gap-3 mb-4 flex-1">
                                    <div className={`p-3 ${iconBg} rounded-lg transition-colors`}>
                                        <Icon className={`w-6 h-6 ${iconColor}`} />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <h3 className="font-semibold text-foreground mb-1 line-clamp-2 pr-16" title={item.filename}>
                                            {item.filename}
                                        </h3>
                                        <div className="text-xs text-muted-foreground">
                                            {getSourceLabel(item.type, item.sourceType)}
                                        </div>
                                    </div>
                                </div>

                                <div className="flex items-center justify-between gap-2 flex-wrap mt-auto">
                                    <div className="flex items-center gap-2 flex-wrap">
                                        {isSlide ? (
                                            <>
                                                {item.pageCount !== undefined && (
                                                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-gray-50 dark:bg-gray-800 text-xs font-medium text-gray-700 dark:text-gray-300">
                                                        <FileText className="w-3 h-3" />
                                                        {item.pageCount} pages
                                                    </span>
                                                )}
                                                {item.videoStatus === "ready" ? (
                                                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-green-50 dark:bg-green-900/20 text-xs font-medium text-green-700 dark:text-green-400">
                                                        <Play className="w-3 h-3" />
                                                        Video ready
                                                    </span>
                                                ) : (
                                                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-orange-50 dark:bg-orange-900/20 text-xs font-medium text-orange-700 dark:text-orange-400">
                                                        <Loader2 className="w-3 h-3" />
                                                        No video yet
                                                    </span>
                                                )}
                                            </>
                                        ) : (
                                            <>
                                                {item.subtitleStatus === "ready" && (
                                                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-green-50 dark:bg-green-900/20 text-xs font-medium text-green-700 dark:text-green-400">
                                                        <FileText className="w-3 h-3" />
                                                        Subtitles
                                                    </span>
                                                )}
                                                {item.translationStatus === "ready" && (
                                                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-purple-50 dark:bg-purple-900/20 text-xs font-medium text-purple-700 dark:text-purple-400">
                                                        <Globe className="w-3 h-3" />
                                                        Translated
                                                    </span>
                                                )}
                                            </>
                                        )}
                                    </div>

                                    <span className="text-xs text-muted-foreground flex items-center gap-1">
                                        <Clock className="w-3 h-3" />
                                        {new Date(item.createdAt).toLocaleDateString()}
                                    </span>
                                </div>
                            </Link>

                            {/* Action Buttons */}
                            <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                <button
                                    onClick={(e) => openRenameDialog(item, e)}
                                    className="p-2 rounded-lg bg-white/90 dark:bg-gray-800/90 text-gray-500 dark:text-gray-400 hover:text-blue-500 dark:hover:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 border border-gray-200 dark:border-gray-700 shadow-sm"
                                    title="Rename"
                                >
                                    <Edit2 className="w-4 h-4" />
                                </button>
                                <button
                                    onClick={(e) => handleDelete(item.id, e)}
                                    disabled={isDeleting}
                                    className="p-2 rounded-lg bg-white/90 dark:bg-gray-800/90 text-gray-500 dark:text-gray-400 hover:text-red-500 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 border border-gray-200 dark:border-gray-700 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                                    title="Delete"
                                >
                                    {isDeleting ? (
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                    ) : (
                                        <Trash2 className="w-4 h-4" />
                                    )}
                                </button>
                            </div>
                        </div>
                    );
                })}
            </div>

            {renameItem && (
                <RenameDialog
                    isOpen={!!renameItem}
                    title="Rename Content"
                    currentName={renameItem.filename}
                    onConfirm={handleRename}
                    onCancel={() => setRenameItem(null)}
                />
            )}
        </>
    );
}

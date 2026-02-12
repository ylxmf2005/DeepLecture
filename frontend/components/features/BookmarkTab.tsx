"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { Bookmark, Plus, Trash2, Clock, Edit3, Check, X, AlertCircle, Loader2 } from "lucide-react";
import { listBookmarks, createBookmark, updateBookmark, deleteBookmark } from "@/lib/api/bookmarks";
import type { BookmarkItem } from "@/lib/api/bookmarks";
import type { Subtitle } from "@/lib/srt";
import { getActiveSubtitles } from "@/lib/subtitleSearch";
import { formatTime } from "@/lib/timeFormat";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";
import { cn } from "@/lib/utils";

const log = logger.scope("BookmarkTab");

interface BookmarkTabProps {
    videoId: string;
    currentTime: number;
    onSeek: (time: number) => void;
    subtitles?: Subtitle[];
    /** Callback when bookmarks change — parent can use this for progress bar markers */
    onBookmarksChange?: (timestamps: number[]) => void;
    /** Incremented by parent to trigger a re-fetch (e.g. after B-key creates a bookmark externally) */
    refreshTrigger?: number;
}

export function BookmarkTab({ videoId, currentTime, onSeek, subtitles, onBookmarksChange, refreshTrigger }: BookmarkTabProps) {
    const [bookmarks, setBookmarks] = useState<BookmarkItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editTitle, setEditTitle] = useState("");
    const [editNote, setEditNote] = useState("");
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);
    const activeRef = useRef<HTMLDivElement>(null);

    // Fetch bookmarks on mount
    const fetchBookmarks = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const result = await listBookmarks(videoId);
            setBookmarks(result.bookmarks);
        } catch (err) {
            log.error("Failed to fetch bookmarks", toError(err));
            setError("Failed to load bookmarks");
        } finally {
            setLoading(false);
        }
    }, [videoId]);

    useEffect(() => {
        fetchBookmarks();
    }, [fetchBookmarks]);

    // Re-fetch when parent signals a change (e.g. B-key created a bookmark externally)
    useEffect(() => {
        if (refreshTrigger) {
            fetchBookmarks();
        }
    }, [refreshTrigger, fetchBookmarks]);

    // Notify parent of bookmark timestamps for progress bar markers
    useEffect(() => {
        onBookmarksChange?.(bookmarks.map((b) => b.timestamp));
    }, [bookmarks, onBookmarksChange]);

    // Find active bookmark: largest timestamp <= currentTime
    const activeBookmarkId = useMemo(() => {
        let best: BookmarkItem | null = null;
        for (const b of bookmarks) {
            if (b.timestamp <= currentTime && (!best || b.timestamp > best.timestamp)) {
                best = b;
            }
        }
        return best?.id ?? null;
    }, [bookmarks, currentTime]);

    // Auto-scroll to active bookmark
    useEffect(() => {
        if (activeRef.current && activeBookmarkId) {
            activeRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    }, [activeBookmarkId]);

    // Get subtitle text at given timestamp for auto-fill
    const getSubtitleAtTime = useCallback(
        (time: number): string => {
            if (!subtitles || subtitles.length === 0) return "";
            const active = getActiveSubtitles(subtitles, time);
            return active.map((s) => s.text).join(" ").trim();
        },
        [subtitles]
    );

    // Add bookmark at current time
    const handleAdd = useCallback(async () => {
        try {
            setSaving(true);
            const subtitleText = getSubtitleAtTime(currentTime);
            const title = subtitleText || `Bookmark at ${formatTime(currentTime)}`;
            const item = await createBookmark(videoId, currentTime, title);
            setBookmarks((prev) => [...prev, item].sort((a, b) => a.timestamp - b.timestamp));
        } catch (err) {
            log.error("Failed to create bookmark", toError(err));
            setError("Failed to create bookmark");
        } finally {
            setSaving(false);
        }
    }, [videoId, currentTime, getSubtitleAtTime]);

    // Start editing a bookmark
    const startEdit = useCallback((bookmark: BookmarkItem) => {
        setEditingId(bookmark.id);
        setEditTitle(bookmark.title);
        setEditNote(bookmark.note);
        setExpandedId(bookmark.id);
    }, []);

    // Save edit
    const saveEdit = useCallback(
        async (id: string) => {
            try {
                setSaving(true);
                const updated = await updateBookmark(id, videoId, {
                    title: editTitle,
                    note: editNote,
                });
                setBookmarks((prev) => prev.map((b) => (b.id === id ? updated : b)));
                setEditingId(null);
            } catch (err) {
                log.error("Failed to update bookmark", toError(err));
                setError("Failed to update bookmark");
            } finally {
                setSaving(false);
            }
        },
        [videoId, editTitle, editNote]
    );

    // Cancel edit
    const cancelEdit = useCallback(() => {
        setEditingId(null);
    }, []);

    // Delete bookmark
    const handleDelete = useCallback(
        async (id: string) => {
            try {
                await deleteBookmark(id, videoId);
                setBookmarks((prev) => prev.filter((b) => b.id !== id));
                setDeleteConfirmId(null);
                if (expandedId === id) setExpandedId(null);
            } catch (err) {
                log.error("Failed to delete bookmark", toError(err));
                setError("Failed to delete bookmark");
            }
        },
        [videoId, expandedId]
    );

    // Toggle expand
    const toggleExpand = useCallback(
        (id: string) => {
            setExpandedId((prev) => (prev === id ? null : id));
            if (editingId && editingId !== id) {
                setEditingId(null);
            }
        },
        [editingId]
    );

    // --- Render ---

    if (loading) {
        return (
            <div className="flex h-full items-center justify-center text-gray-500">
                <Loader2 className="w-5 h-5 animate-spin mr-2" />
                <span className="text-sm">Loading bookmarks...</span>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full min-h-0">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-muted/30">
                <div className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
                    <Bookmark className="w-4 h-4" />
                    <span>Bookmarks</span>
                    {bookmarks.length > 0 && (
                        <span className="text-xs text-gray-400">({bookmarks.length})</span>
                    )}
                </div>
                <button
                    onClick={handleAdd}
                    disabled={saving}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md
                        bg-yellow-500/10 text-yellow-700 dark:text-yellow-400
                        hover:bg-yellow-500/20 disabled:opacity-50 transition-colors"
                    title="Add bookmark at current time (B)"
                >
                    <Plus className="w-3.5 h-3.5" />
                    Add Bookmark
                </button>
            </div>

            {/* Error */}
            {error && (
                <div className="flex items-center gap-2 px-4 py-2 text-xs text-red-600 bg-red-50 dark:bg-red-900/20 dark:text-red-400">
                    <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                    {error}
                    <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-600">
                        <X className="w-3 h-3" />
                    </button>
                </div>
            )}

            {/* List */}
            <div className="flex-1 overflow-y-auto min-h-0">
                {bookmarks.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-gray-500 gap-3 p-8 text-center">
                        <Bookmark className="w-12 h-12 opacity-20" />
                        <p className="text-sm">No bookmarks yet</p>
                        <p className="text-xs text-gray-400">
                            Click &quot;Add Bookmark&quot; or press <kbd className="px-1.5 py-0.5 rounded bg-gray-200 dark:bg-gray-700 text-xs font-mono">B</kbd> to bookmark the current position
                        </p>
                    </div>
                ) : (
                    <div className="divide-y divide-border">
                        {bookmarks.map((bookmark) => {
                            const isActive = bookmark.id === activeBookmarkId;
                            const isExpanded = bookmark.id === expandedId;
                            const isEditing = bookmark.id === editingId;
                            const isConfirmingDelete = bookmark.id === deleteConfirmId;

                            return (
                                <div
                                    key={bookmark.id}
                                    ref={isActive ? activeRef : undefined}
                                    className={cn(
                                        "group transition-colors",
                                        isActive && "bg-yellow-50/50 dark:bg-yellow-900/10 border-l-2 border-l-yellow-400",
                                        !isActive && "border-l-2 border-l-transparent"
                                    )}
                                >
                                    {/* Row header */}
                                    <div className="flex items-start gap-3 px-4 py-3">
                                        {/* Timestamp badge */}
                                        <button
                                            onClick={() => onSeek(bookmark.timestamp)}
                                            className="flex-shrink-0 flex items-center gap-1 px-2 py-1 text-xs font-mono
                                                rounded bg-gray-100 dark:bg-gray-800 text-blue-600 dark:text-blue-400
                                                hover:bg-blue-100 dark:hover:bg-blue-900/30 transition-colors"
                                            title={`Jump to ${formatTime(bookmark.timestamp)}`}
                                        >
                                            <Clock className="w-3 h-3" />
                                            {formatTime(bookmark.timestamp)}
                                        </button>

                                        {/* Title + note preview */}
                                        <div className="flex-1 min-w-0">
                                            {isEditing ? (
                                                <input
                                                    type="text"
                                                    value={editTitle}
                                                    onChange={(e) => setEditTitle(e.target.value)}
                                                    className="w-full px-2 py-1 text-sm border rounded bg-background"
                                                    autoFocus
                                                    onKeyDown={(e) => {
                                                        if (e.key === "Enter") saveEdit(bookmark.id);
                                                        if (e.key === "Escape") cancelEdit();
                                                    }}
                                                />
                                            ) : (
                                                <button
                                                    onClick={() => toggleExpand(bookmark.id)}
                                                    className="text-left w-full"
                                                >
                                                    <p className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
                                                        {bookmark.title || "Untitled Bookmark"}
                                                    </p>
                                                    {bookmark.note && !isExpanded && (
                                                        <p className="text-xs text-gray-400 truncate mt-0.5">
                                                            {bookmark.note.slice(0, 80)}{bookmark.note.length > 80 ? "..." : ""}
                                                        </p>
                                                    )}
                                                </button>
                                            )}
                                        </div>

                                        {/* Actions */}
                                        <div className="flex-shrink-0 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                            {isEditing ? (
                                                <>
                                                    <button
                                                        onClick={() => saveEdit(bookmark.id)}
                                                        disabled={saving}
                                                        className="p-1 rounded text-green-600 hover:bg-green-100 dark:hover:bg-green-900/30"
                                                        title="Save"
                                                    >
                                                        <Check className="w-3.5 h-3.5" />
                                                    </button>
                                                    <button
                                                        onClick={cancelEdit}
                                                        className="p-1 rounded text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
                                                        title="Cancel"
                                                    >
                                                        <X className="w-3.5 h-3.5" />
                                                    </button>
                                                </>
                                            ) : (
                                                <>
                                                    <button
                                                        onClick={() => startEdit(bookmark)}
                                                        className="p-1 rounded text-gray-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30"
                                                        title="Edit"
                                                    >
                                                        <Edit3 className="w-3.5 h-3.5" />
                                                    </button>
                                                    <button
                                                        onClick={() => setDeleteConfirmId(bookmark.id)}
                                                        className="p-1 rounded text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30"
                                                        title="Delete"
                                                    >
                                                        <Trash2 className="w-3.5 h-3.5" />
                                                    </button>
                                                </>
                                            )}
                                        </div>
                                    </div>

                                    {/* Delete confirmation */}
                                    {isConfirmingDelete && (
                                        <div className="flex items-center gap-2 px-4 py-2 bg-red-50 dark:bg-red-900/20 text-xs">
                                            <span className="text-red-600 dark:text-red-400">Delete this bookmark?</span>
                                            <button
                                                onClick={() => handleDelete(bookmark.id)}
                                                className="px-2 py-1 rounded bg-red-600 text-white hover:bg-red-700 text-xs"
                                            >
                                                Delete
                                            </button>
                                            <button
                                                onClick={() => setDeleteConfirmId(null)}
                                                className="px-2 py-1 rounded bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 text-xs"
                                            >
                                                Cancel
                                            </button>
                                        </div>
                                    )}

                                    {/* Expanded note editor */}
                                    {isExpanded && (
                                        <div className="px-4 pb-3">
                                            {isEditing ? (
                                                <textarea
                                                    value={editNote}
                                                    onChange={(e) => setEditNote(e.target.value)}
                                                    placeholder="Add a note..."
                                                    rows={4}
                                                    className="w-full px-3 py-2 text-sm border rounded bg-background resize-y min-h-[80px]"
                                                />
                                            ) : (
                                                <div className="text-sm text-gray-600 dark:text-gray-400 whitespace-pre-wrap">
                                                    {bookmark.note || (
                                                        <span className="text-gray-400 italic">No note. Click edit to add one.</span>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}

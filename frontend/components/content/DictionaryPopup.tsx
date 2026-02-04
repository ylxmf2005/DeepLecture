"use client";

/**
 * DictionaryPopup
 *
 * Floating popup that displays word definitions, pronunciation, and save button.
 */

import { memo, useCallback, useEffect, useRef, useState } from "react";
import { X, BookmarkPlus, BookmarkCheck, Loader2 } from "lucide-react";
import type { DictionaryEntry } from "@/lib/dictionary/types";
import { cn } from "@/lib/utils";

interface DictionaryPopupProps {
    /** The anchor rectangle to position near */
    anchorRect: DOMRect | null;
    /** Dictionary entry to display */
    entry: DictionaryEntry | null;
    /** Whether lookup is in progress */
    loading?: boolean;
    /** Error message */
    error?: string | null;
    /** Whether this word is already saved */
    isSaved?: boolean;
    /** Called when save button is clicked */
    onSave?: () => void;
    /** Called when close button is clicked or user clicks outside */
    onClose?: () => void;
}

/**
 * Calculate popup position based on anchor rect
 * Ensures popup stays within viewport
 */
function calculatePosition(
    anchorRect: DOMRect,
    popupWidth: number,
    popupHeight: number
): { top: number; left: number } {
    const padding = 8;
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    // Default: position below the word
    let top = anchorRect.bottom + padding;
    let left = anchorRect.left + anchorRect.width / 2 - popupWidth / 2;

    // Keep within horizontal bounds
    if (left < padding) {
        left = padding;
    } else if (left + popupWidth > viewportWidth - padding) {
        left = viewportWidth - popupWidth - padding;
    }

    // If popup would go below viewport, position above the word
    if (top + popupHeight > viewportHeight - padding) {
        top = anchorRect.top - popupHeight - padding;
    }

    // Keep within vertical bounds
    if (top < padding) {
        top = padding;
    }

    return { top, left };
}

function DictionaryPopupBase({
    anchorRect,
    entry,
    loading = false,
    error = null,
    isSaved = false,
    onSave,
    onClose,
}: DictionaryPopupProps) {
    const popupRef = useRef<HTMLDivElement>(null);
    const [position, setPosition] = useState({ top: 0, left: 0 });
    const [visible, setVisible] = useState(false);

    // Calculate position when anchor or content changes
    useEffect(() => {
        if (!anchorRect) {
            setVisible(false);
            return;
        }

        // Wait for next frame to measure popup
        requestAnimationFrame(() => {
            if (popupRef.current) {
                const rect = popupRef.current.getBoundingClientRect();
                const pos = calculatePosition(anchorRect, rect.width, rect.height);
                setPosition(pos);
                setVisible(true);
            }
        });
    }, [anchorRect, entry, loading, error]);

    // Close on escape key
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") {
                onClose?.();
            }
        };

        document.addEventListener("keydown", handleKeyDown);
        return () => document.removeEventListener("keydown", handleKeyDown);
    }, [onClose]);

    // Handle click outside
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (
                popupRef.current &&
                !popupRef.current.contains(e.target as Node)
            ) {
                onClose?.();
            }
        };

        // Delay adding listener to avoid immediate close
        const timer = setTimeout(() => {
            document.addEventListener("mousedown", handleClickOutside);
        }, 100);

        return () => {
            clearTimeout(timer);
            document.removeEventListener("mousedown", handleClickOutside);
        };
    }, [onClose]);

    const handleSaveClick = useCallback(() => {
        onSave?.();
    }, [onSave]);

    if (!anchorRect) {
        return null;
    }

    const showContent = !loading && !error && entry;

    return (
        <div
            ref={popupRef}
            role="tooltip"
            className={cn(
                "fixed z-50 w-80 max-w-[90vw] rounded-lg shadow-xl",
                "bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700",
                "transition-opacity duration-150",
                visible ? "opacity-100" : "opacity-0"
            )}
            style={{
                top: position.top,
                left: position.left,
            }}
        >
            {/* Header */}
            <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-gray-700">
                <div className="flex items-center gap-2">
                    {showContent && (
                        <>
                            <span className="font-semibold text-gray-900 dark:text-gray-100">
                                {entry.word}
                            </span>
                            {entry.phonetic && (
                                <span className="text-sm text-gray-500 dark:text-gray-400">
                                    {entry.phonetic}
                                </span>
                            )}
                        </>
                    )}
                    {loading && (
                        <span className="text-sm text-gray-500">Looking up...</span>
                    )}
                    {error && (
                        <span className="text-sm text-gray-500">{error}</span>
                    )}
                </div>
                <div className="flex items-center gap-1">
                    {showContent && onSave && (
                        <button
                            onClick={handleSaveClick}
                            disabled={isSaved}
                            className={cn(
                                "p-1 rounded transition-colors",
                                isSaved
                                    ? "text-green-600 dark:text-green-400 cursor-default"
                                    : "text-gray-500 hover:text-blue-600 dark:hover:text-blue-400"
                            )}
                            title={isSaved ? "Saved to vocabulary" : "Save to vocabulary"}
                        >
                            {isSaved ? (
                                <BookmarkCheck className="w-4 h-4" />
                            ) : (
                                <BookmarkPlus className="w-4 h-4" />
                            )}
                        </button>
                    )}
                    <button
                        onClick={onClose}
                        className="p-1 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 rounded transition-colors"
                        title="Close"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>
            </div>

            {/* Content */}
            <div className="px-3 py-2 max-h-60 overflow-y-auto">
                {loading && (
                    <div className="flex items-center justify-center py-4">
                        <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
                    </div>
                )}

                {error && !loading && (
                    <p className="text-sm text-gray-500 dark:text-gray-400 italic">
                        {error === "Word not found"
                            ? "No definition found for this word."
                            : "Failed to look up this word. Please try again."}
                    </p>
                )}

                {showContent && (
                    <div className="space-y-2">
                        {entry.definitions.slice(0, 3).map((def, index) => (
                            <div key={index} className="text-sm">
                                <span className="text-gray-500 dark:text-gray-400 italic">
                                    {def.partOfSpeech}
                                </span>
                                <p className="text-gray-800 dark:text-gray-200 mt-0.5">
                                    {def.meaning}
                                </p>
                                {def.example && (
                                    <p className="text-gray-500 dark:text-gray-400 text-xs mt-0.5 italic">
                                        "{def.example}"
                                    </p>
                                )}
                            </div>
                        ))}
                        {entry.definitions.length > 3 && (
                            <p className="text-xs text-gray-400">
                                +{entry.definitions.length - 3} more definitions
                            </p>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

export const DictionaryPopup = memo(DictionaryPopupBase);

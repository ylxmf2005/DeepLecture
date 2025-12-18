"use client";

import { useEffect, useRef, memo, useMemo, useCallback } from "react";
import { Virtuoso, VirtuosoHandle } from "react-virtuoso";
import { cn } from "@/lib/utils";
import { formatTime } from "@/lib/timeFormat";
import { Subtitle } from "@/lib/srt";
import { binarySearchSubtitle } from "@/lib/subtitleSearch";
import { MessageSquare, FilePlus } from "lucide-react";
import type { AskContextItem } from "@/lib/askTypes";

interface SubtitleListProps {
    subtitles: Subtitle[];
    currentTime: number;
    onSeek: (time: number) => void;
    onAddToAsk: (item: AskContextItem) => void;
    onAddToNotes?: (markdown: string) => void;
}

// Position active subtitle at 22% from top (instead of 50% center)
const SCROLL_POSITION_RATIO = 0.22;

function SubtitleListBase({ subtitles, currentTime, onSeek, onAddToAsk, onAddToNotes }: SubtitleListProps) {
    const virtuosoRef = useRef<VirtuosoHandle>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const lastScrolledIndexRef = useRef<number>(-1);
    const hasInitialScrolledRef = useRef<boolean>(false);

    // Binary-search to locate the active subtitle (O(log n))
    const activeIndex = useMemo(() => {
        const idx = binarySearchSubtitle(subtitles, currentTime);
        if (idx >= 0) return idx;

        // Fallback: find the last subtitle that started before current time
        for (let i = subtitles.length - 1; i >= 0; i--) {
            if (subtitles[i].startTime <= currentTime) {
                return i;
            }
        }
        return -1;
    }, [subtitles, currentTime]);

    // Centralized scroll function - positions item at 33% from top
    const scrollToActiveSubtitle = useCallback((behavior: "smooth" | "auto" = "smooth") => {
        if (virtuosoRef.current && activeIndex >= 0 && containerRef.current) {
            const containerHeight = containerRef.current.clientHeight;
            // align: "start" puts item at top, negative offset moves viewport up (item moves down)
            const offset = -containerHeight * SCROLL_POSITION_RATIO;
            virtuosoRef.current.scrollToIndex({
                index: activeIndex,
                align: "start",
                offset,
                behavior,
            });
        }
    }, [activeIndex]);

    // Auto-scroll when activeIndex changes during playback
    useEffect(() => {
        if (activeIndex >= 0 && lastScrolledIndexRef.current !== activeIndex) {
            lastScrolledIndexRef.current = activeIndex;
            scrollToActiveSubtitle("smooth");
        }
    }, [activeIndex, scrollToActiveSubtitle]);

    // Initial scroll when subtitles first load or change
    useEffect(() => {
        if (subtitles.length > 0 && activeIndex >= 0 && !hasInitialScrolledRef.current) {
            hasInitialScrolledRef.current = true;
            // Use requestAnimationFrame to ensure Virtuoso has measured items
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    scrollToActiveSubtitle("auto");
                });
            });
        }
    }, [subtitles.length, activeIndex, scrollToActiveSubtitle]);

    // Reset initial scroll flag when subtitles array changes (different video)
    useEffect(() => {
        hasInitialScrolledRef.current = false;
        lastScrolledIndexRef.current = -1;
    }, [subtitles]);

    // Handle tab visibility change - re-center when returning to tab
    useEffect(() => {
        const handleVisibilityChange = () => {
            if (document.visibilityState === "visible" && activeIndex >= 0) {
                // Reset to allow re-scroll
                lastScrolledIndexRef.current = -1;
                requestAnimationFrame(() => {
                    scrollToActiveSubtitle("auto");
                });
            }
        };

        document.addEventListener("visibilitychange", handleVisibilityChange);
        return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
    }, [activeIndex, scrollToActiveSubtitle]);

    return (
        <div ref={containerRef} className="h-full bg-background rounded-lg border border-border">
            <Virtuoso
                ref={virtuosoRef}
                style={{ height: "100%" }}
                totalCount={subtitles.length}
                overscan={30}
                itemContent={(index) => {
                    const subtitle = subtitles[index];
                    const isActive = index === activeIndex;

                    return (
                        <div
                            onClick={() => onSeek(subtitle.startTime)}
                            className={cn(
                                "p-3 rounded-lg cursor-pointer transition-all duration-200 group relative mx-2 mb-2",
                                isActive
                                    ? "bg-blue-100 dark:bg-blue-900/40 border-l-4 border-blue-500 shadow-sm"
                                    : "hover:bg-muted text-muted-foreground"
                            )}
                        >
                            <div className="flex justify-between text-xs text-gray-400 mb-1">
                                <span>{formatTime(subtitle.startTime)}</span>
                                <div className="flex items-center gap-1">
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            onAddToAsk({
                                                type: "subtitle",
                                                id: `subtitle-${subtitle.id}`,
                                                text: subtitle.text,
                                                startTime: subtitle.startTime,
                                            });
                                        }}
                                        className="opacity-0 group-hover:opacity-100 p-1 hover:text-blue-500 transition-opacity"
                                        title="Ask AI about this"
                                    >
                                        <MessageSquare className="w-3 h-3" />
                                    </button>
                                    {onAddToNotes && (
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                const snippet = `- [${formatTime(subtitle.startTime)}] ${subtitle.text}`;
                                                onAddToNotes(snippet);
                                            }}
                                            className="opacity-0 group-hover:opacity-100 p-1 hover:text-emerald-600 transition-opacity"
                                            title="Add to notes"
                                        >
                                            <FilePlus className="w-3 h-3" />
                                        </button>
                                    )}
                                </div>
                            </div>
                            <p
                                className={cn(
                                    "text-sm leading-relaxed whitespace-pre-wrap pr-6",
                                    isActive ? "text-gray-900 dark:text-gray-100 font-medium" : ""
                                )}
                            >
                                {subtitle.text}
                            </p>
                        </div>
                    );
                }}
            />
        </div>
    );
}

export const SubtitleList = memo(SubtitleListBase);

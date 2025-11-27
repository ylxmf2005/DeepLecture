"use client";

import { useEffect, useRef, memo, useMemo } from "react";
import { List, useListRef, useDynamicRowHeight } from "react-window";
import type { RowComponentProps } from "react-window";
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

interface SubtitleRowProps {
    subtitle: Subtitle;
    isActive: boolean;
    onSeek: (time: number) => void;
    onAddToAsk: (item: AskContextItem) => void;
    onAddToNotes?: (markdown: string) => void;
}

const SubtitleRow = memo(function SubtitleRow({
    subtitle,
    isActive,
    onSeek,
    onAddToAsk,
    onAddToNotes,
}: SubtitleRowProps) {
    const rowRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (isActive && rowRef.current) {
            const element = rowRef.current;

            // Find scrollable container
            let container = element.parentElement;
            while (container && container.scrollHeight <= container.clientHeight) {
                container = container.parentElement;
            }
            if (!container) return;

            const elementRect = element.getBoundingClientRect();
            const screenCenter = window.innerHeight / 2;
            const elementCenter = elementRect.top + elementRect.height / 2;
            const scrollDelta = elementCenter - screenCenter;
            const targetScroll = container.scrollTop + scrollDelta;

            // Check if element is on screen
            const isOnScreen = elementRect.top >= 0 && elementRect.bottom <= window.innerHeight;

            // Only scroll if: not on screen, OR centering requires scrolling UP
            if (!isOnScreen || scrollDelta < 0) {
                container.scrollTo({
                    top: targetScroll,
                    behavior: "smooth"
                });
            }
        }
    }, [isActive]);

    return (
        <div ref={rowRef} className="scroll-mt-32">
            <div
                onClick={() => onSeek(subtitle.startTime)}
                className={cn(
                    "p-3 rounded-lg cursor-pointer transition-all duration-200 group relative mx-2",
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
        </div>
    );
});

// Data shape for the virtualized row component
interface VirtualRowData {
    subtitles: Subtitle[];
    activeIndex: number;
    onSeek: (time: number) => void;
    onAddToAsk: (item: AskContextItem) => void;
    onAddToNotes?: (markdown: string) => void;
}

// Virtual row renderer (react-window v2 API with dynamic height)
function VirtualSubtitleRow({
    index,
    style,
    subtitles,
    activeIndex,
    onSeek,
    onAddToAsk,
    onAddToNotes,
}: RowComponentProps<VirtualRowData> & VirtualRowData) {
    const subtitle = subtitles[index];
    const isActive = index === activeIndex;

    return (
        <div style={style} data-react-window-index={index}>
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
        </div>
    );
}

// Default row height for initial render before measurement
const DEFAULT_ROW_HEIGHT = 80;

function SubtitleListBase({ subtitles, currentTime, onSeek, onAddToAsk, onAddToNotes }: SubtitleListProps) {
    const listRef = useListRef(null);
    const containerRef = useRef<HTMLDivElement>(null);

    // Use react-window v2's built-in dynamic row height with ResizeObserver
    const dynamicRowHeight = useDynamicRowHeight({ defaultRowHeight: DEFAULT_ROW_HEIGHT });

    // Binary-search to locate the active subtitle (O(log n) instead of O(n))
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

    // Data passed to each row
    const rowProps = useMemo<VirtualRowData>(
        () => ({
            subtitles,
            activeIndex,
            onSeek,
            onAddToAsk,
            onAddToNotes,
        }),
        [subtitles, activeIndex, onSeek, onAddToAsk, onAddToNotes]
    );

    // Auto-scroll to keep the active subtitle centered
    useEffect(() => {
        if (listRef.current && activeIndex >= 0) {
            listRef.current.scrollToRow({
                index: activeIndex,
                align: "center",
                behavior: "smooth"
            });
        }
    }, [activeIndex, listRef]);

    // Simple render when subtitles are few
    if (subtitles.length < 50) {
        return (
            <div className="h-full overflow-y-auto p-4 space-y-2 bg-background rounded-lg border border-border">
                {subtitles.map((sub, index) => (
                    <SubtitleRow
                        key={sub.id}
                        subtitle={sub}
                        isActive={index === activeIndex}
                        onSeek={onSeek}
                        onAddToAsk={onAddToAsk}
                        onAddToNotes={onAddToNotes}
                    />
                ))}
            </div>
        );
    }

    // Virtualized list with dynamic row heights (react-window v2 API)
    return (
        <div
            ref={containerRef}
            className="h-full bg-background rounded-lg border border-border"
        >
            <List
                listRef={listRef}
                rowComponent={VirtualSubtitleRow}
                rowCount={subtitles.length}
                rowHeight={dynamicRowHeight}
                rowProps={rowProps}
                overscanCount={5}
                style={{ height: "100%", width: "100%" }}
            />
        </div>
    );
}

export const SubtitleList = memo(SubtitleListBase, (prevProps, nextProps) => {
    return (
        prevProps.subtitles === nextProps.subtitles &&
        prevProps.currentTime === nextProps.currentTime &&
        (prevProps.onAddToNotes === undefined) === (nextProps.onAddToNotes === undefined)
    );
});

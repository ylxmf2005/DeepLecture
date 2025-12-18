import { TimelineEntry } from "@/lib/api";
import { formatTime } from "@/lib/timeFormat";
import { MarkdownRenderer } from "@/components/editor/MarkdownRenderer";
import { Clock, ChevronRight, PlayCircle, MessageSquare, FilePlus } from "lucide-react";
import { useState, useRef, useEffect, memo } from "react";
import { cn } from "@/lib/utils";
import type { AskContextItem } from "@/lib/askTypes";

interface TimelineListProps {
    entries: TimelineEntry[];
    onSeek: (time: number) => void;
    currentTime?: number;
    className?: string;
    onAddToAsk: (item: AskContextItem) => void;
    onAddToNotes?: (markdown: string) => void;
    onGenerate?: () => void;
    isGenerating?: boolean;
}

function TimelineListBase({
    entries,
    onSeek,
    currentTime = 0,
    className,
    onAddToAsk,
    onAddToNotes,
    onGenerate,
    isGenerating = false,
}: TimelineListProps) {
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const itemRefs = useRef<{ [key: string]: HTMLDivElement | null }>({});

    // Identify the active timeline entry based on current time
    const activeIndex = entries.findIndex(
        (item) => currentTime >= item.start && currentTime < item.end
    );
    const activeId = activeIndex !== -1 ? `timeline-entry-${activeIndex}` : null;

    // Auto-scroll to active item
    useEffect(() => {
        if (activeId && itemRefs.current[activeId] && scrollContainerRef.current) {
            const element = itemRefs.current[activeId];
            const container = scrollContainerRef.current;
            if (!element || !container) return;

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
    }, [activeId]);

    if (!entries || entries.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground p-8 text-center">
                <Clock className="w-12 h-12 opacity-20 mb-4" />
                <p>No timeline entries available yet.</p>
                {onGenerate && (
                    <button
                        onClick={onGenerate}
                        disabled={isGenerating}
                        className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors font-medium text-sm"
                    >
                        {isGenerating ? "Generating..." : "Generate Timeline"}
                    </button>
                )}
            </div>
        );
    }

    return (
        <div
            ref={scrollContainerRef}
            className={cn("h-full overflow-y-auto p-6 relative custom-scrollbar", className)}
        >
            {/* Vertical Line */}
            <div className="absolute left-[39px] top-6 bottom-6 w-0.5 bg-border" />

            <div className="space-y-6">
                {entries.map((item, index) => {
                    const itemId = `timeline-entry-${index}`;
                    // If the user has clicked an item, respect that choice.
                    // Otherwise, auto-expand the currently active entry.
                    const isExpanded = expandedId ? expandedId === itemId : activeId === itemId;
                    const isActive = activeId === itemId;

                    return (
                        <div
                            key={index}
                            className="relative pl-10"
                            ref={(el) => { itemRefs.current[itemId] = el; }}
                        >
                            {/* Dot */}
                            <div
                                className={cn(
                                    "absolute left-6 top-1.5 w-4 h-4 rounded-full border-2 z-10 transform -translate-x-1/2 transition-all duration-300",
                                    isActive
                                        ? "border-primary bg-primary scale-125 shadow-[0_0_10px_rgba(59,130,246,0.5)]"
                                        : isExpanded
                                            ? "border-primary bg-primary"
                                            : "border-muted-foreground bg-background"
                                )}
                            />

                            <div
                                className={cn(
                                    "bg-card border rounded-lg p-4 transition-all cursor-pointer hover:shadow-md group",
                                    isActive
                                        ? "border-primary ring-1 ring-primary shadow-md bg-primary/5"
                                        : isExpanded
                                            ? "border-primary/50 ring-1 ring-primary/20 shadow-sm"
                                            : "border-border hover:border-primary/40"
                                )}
                                onClick={() =>
                                    setExpandedId((prev) => (prev === itemId ? null : itemId))
                                }
                            >
                                <div className="flex items-start justify-between gap-3">
                                    <div className="flex flex-col gap-1">
                                        <div className="inline-flex items-center gap-2 text-xs text-muted-foreground">
                                            <Clock className="w-3 h-3" />
                                            <span>
                                                {formatTime(item.start)} - {formatTime(item.end)}
                                            </span>
                                        </div>
                                        <h3 className="text-sm font-semibold leading-snug">
                                            {item.title}
                                        </h3>
                                    </div>

                                    <div className="flex items-center gap-1">
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                onAddToAsk({
                                                    type: "timeline",
                                                    id: `timeline-${index}`,
                                                    title: item.title,
                                                    content: item.markdown,
                                                    start: item.start,
                                                    end: item.end,
                                                });
                                            }}
                                            className="p-1.5 rounded-full text-muted-foreground hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors opacity-0 group-hover:opacity-100"
                                            title="Ask AI about this"
                                        >
                                            <MessageSquare className="w-4 h-4" />
                                        </button>
                                        {onAddToNotes && (
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    const heading = `### ${item.title} (${formatTime(item.start)} - ${formatTime(item.end)})`;
                                                    const snippet = `${heading}\n\n${item.markdown}`;
                                                    onAddToNotes(snippet);
                                                }}
                                                className="p-1.5 rounded-full text-muted-foreground hover:text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-900/20 transition-colors opacity-0 group-hover:opacity-100"
                                                title="Add to notes"
                                            >
                                                <FilePlus className="w-4 h-4" />
                                            </button>
                                        )}
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                onSeek(item.start);
                                            }}
                                            className={cn(
                                                "p-1.5 rounded-full transition-colors focus:opacity-100",
                                                isActive
                                                    ? "text-primary bg-primary/10 opacity-100"
                                                    : "text-muted-foreground hover:text-primary hover:bg-primary/10 opacity-0 group-hover:opacity-100"
                                            )}
                                            title="Jump to this section"
                                        >
                                            <PlayCircle className="w-5 h-5" />
                                        </button>
                                        <ChevronRight
                                            className={cn(
                                                "w-5 h-5 text-muted-foreground transition-transform duration-200",
                                                isExpanded ? "rotate-90" : ""
                                            )}
                                        />
                                    </div>
                                </div>

                                <div
                                    className={cn(
                                        "grid transition-all duration-300 ease-in-out",
                                        isExpanded
                                            ? "grid-rows-[1fr] opacity-100 mt-4"
                                            : "grid-rows-[0fr] opacity-0"
                                    )}
                                >
                                    <div className="overflow-hidden">
                                        <div className="pt-4 border-t border-border/50 prose dark:prose-invert prose-sm max-w-none">
                                            <MarkdownRenderer onSeek={onSeek}>{item.markdown}</MarkdownRenderer>
                                        </div>
                                    </div>
                                </div>

                                {!isExpanded && (
                                    <p className="mt-2 text-sm text-muted-foreground line-clamp-2">
                                        {item.markdown.replace(/[#*`]/g, "")}
                                    </p>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

// Memoized to prevent re-renders when only callbacks change
export const TimelineList = memo(TimelineListBase, (prevProps, nextProps) => {
    // Re-render only when entries, currentTime, className, or isGenerating changes
    return (
        prevProps.entries === nextProps.entries &&
        prevProps.currentTime === nextProps.currentTime &&
        prevProps.className === nextProps.className &&
        prevProps.isGenerating === nextProps.isGenerating &&
        (prevProps.onGenerate === undefined) === (nextProps.onGenerate === undefined) &&
        (prevProps.onAddToNotes === undefined) === (nextProps.onAddToNotes === undefined)
    );
});

"use client";

import { useEffect, useRef, memo, useMemo, useCallback, useState } from "react";
import { Virtuoso, VirtuosoHandle } from "react-virtuoso";
import { cn } from "@/lib/utils";
import { formatTime } from "@/lib/timeFormat";
import { Subtitle } from "@/lib/srt";
import { binarySearchSubtitle } from "@/lib/subtitleSearch";
import { MessageSquare, FilePlus } from "lucide-react";
import type { AskContextItem } from "@/lib/askTypes";
import type { SubtitleDisplayMode } from "@/stores/types";
import {
    createSubtitleRows,
    isSourceFirst,
    type SubtitleRow,
} from "@/lib/subtitles/display";
import {
    HoverableSubtitleText,
    type WordContext,
} from "./HoverableSubtitleText";
import { DictionaryPopup } from "./DictionaryPopup";
import { useDictionaryLookup } from "@/hooks/useDictionaryLookup";
import { useVocabularyStore } from "@/stores/useVocabularyStore";
import { useDictionarySettings } from "@/stores/useGlobalSettingsStore";

interface SubtitleListProps {
    /** Legacy prop - combined subtitles (used when subtitlesSource/Target not provided) */
    subtitles: Subtitle[];
    /** Source language subtitles */
    subtitlesSource?: Subtitle[];
    /** Target language subtitles */
    subtitlesTarget?: Subtitle[];
    /** Subtitle display mode */
    subtitleMode?: SubtitleDisplayMode;
    /** Original language code for dictionary lookups */
    originalLanguage?: string;
    /** Video ID for vocabulary context */
    videoId?: string;
    currentTime: number;
    onSeek: (time: number) => void;
    onAddToAsk: (item: AskContextItem) => void;
    onAddToNotes?: (markdown: string) => void;
}

// Position active subtitle at 22% from top (instead of 50% center)
const SCROLL_POSITION_RATIO = 0.22;

function SubtitleListBase({
    subtitles,
    subtitlesSource,
    subtitlesTarget,
    subtitleMode = "source",
    originalLanguage = "en",
    videoId = "",
    currentTime,
    onSeek,
    onAddToAsk,
    onAddToNotes,
}: SubtitleListProps) {
    const virtuosoRef = useRef<VirtuosoHandle>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const lastScrolledIndexRef = useRef<number>(-1);
    const hasInitialScrolledRef = useRef<boolean>(false);

    // Dictionary lookup state
    const {
        entry,
        loading: lookupLoading,
        error: lookupError,
        lookup,
        clear: clearLookup,
        supports,
    } = useDictionaryLookup({ debounceMs: 200 });

    const [popupAnchor, setPopupAnchor] = useState<DOMRect | null>(null);
    const [currentWordContext, setCurrentWordContext] =
        useState<WordContext | null>(null);

    // Vocabulary store
    const addVocabulary = useVocabularyStore((state) => state.add);
    const hasVocabulary = useVocabularyStore((state) => state.has);

    // Dictionary settings
    const dictionarySettings = useDictionarySettings();

    // Create subtitle rows with separate source/target
    const rows: SubtitleRow[] = useMemo(() => {
        if (subtitlesSource && subtitlesTarget) {
            return createSubtitleRows({
                mode: subtitleMode,
                subtitlesSource,
                subtitlesTarget,
            });
        }

        // Fallback to legacy subtitles (source-only)
        return subtitles.map((sub) => ({
            id: sub.id,
            startTime: sub.startTime,
            endTime: sub.endTime,
            sourceText: sub.text,
        }));
    }, [subtitles, subtitlesSource, subtitlesTarget, subtitleMode]);

    // Binary-search to locate the active subtitle (O(log n))
    const activeIndex = useMemo(() => {
        const idx = binarySearchSubtitle(
            rows.map((r) => ({
                id: r.id,
                startTime: r.startTime,
                endTime: r.endTime,
                text: r.sourceText || r.targetText || "",
            })),
            currentTime
        );
        if (idx >= 0) return idx;

        // Fallback: find the last subtitle that started before current time
        for (let i = rows.length - 1; i >= 0; i--) {
            if (rows[i].startTime <= currentTime) {
                return i;
            }
        }
        return -1;
    }, [rows, currentTime]);

    // Centralized scroll function - positions item at 33% from top
    const scrollToActiveSubtitle = useCallback(
        (behavior: "smooth" | "auto" = "smooth") => {
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
        },
        [activeIndex]
    );

    // Auto-scroll when activeIndex changes during playback
    useEffect(() => {
        if (activeIndex >= 0 && lastScrolledIndexRef.current !== activeIndex) {
            lastScrolledIndexRef.current = activeIndex;
            scrollToActiveSubtitle("smooth");
        }
    }, [activeIndex, scrollToActiveSubtitle]);

    // Initial scroll when subtitles first load or change
    useEffect(() => {
        if (rows.length > 0 && activeIndex >= 0 && !hasInitialScrolledRef.current) {
            hasInitialScrolledRef.current = true;
            // Use requestAnimationFrame to ensure Virtuoso has measured items
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    scrollToActiveSubtitle("auto");
                });
            });
        }
    }, [rows.length, activeIndex, scrollToActiveSubtitle]);

    // Reset initial scroll flag when subtitles array changes (different video)
    useEffect(() => {
        hasInitialScrolledRef.current = false;
        lastScrolledIndexRef.current = -1;
    }, [rows]);

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
        return () =>
            document.removeEventListener("visibilitychange", handleVisibilityChange);
    }, [activeIndex, scrollToActiveSubtitle]);

    // Handle word hover for dictionary lookup
    const handleWordHover = useCallback(
        (word: string, locale: string, rect: DOMRect, context: WordContext) => {
            setPopupAnchor(rect);
            setCurrentWordContext(context);
            lookup(word, locale);
        },
        [lookup]
    );

    // Handle word leave
    const handleWordLeave = useCallback(() => {
        // Don't close immediately - let user move to popup
        // Popup handles its own click-outside closing
    }, []);

    // Handle popup close
    const handlePopupClose = useCallback(() => {
        setPopupAnchor(null);
        setCurrentWordContext(null);
        clearLookup();
    }, [clearLookup]);

    // Handle save to vocabulary
    const handleSaveVocabulary = useCallback(() => {
        if (!entry || !currentWordContext) return;

        const firstDefinition = entry.definitions[0];
        addVocabulary({
            word: entry.word,
            locale: currentWordContext.locale,
            definition: firstDefinition?.meaning || "",
            phonetic: entry.phonetic,
            audioUrl: entry.audioUrl,
            context: {
                videoId: currentWordContext.videoId,
                timestamp: currentWordContext.timestamp,
                sentence: currentWordContext.sentence,
            },
        });
    }, [entry, currentWordContext, addVocabulary]);

    // Check if current word is saved
    const isCurrentWordSaved = useMemo(() => {
        if (!currentWordContext) return false;
        return hasVocabulary(currentWordContext.word, currentWordContext.locale);
    }, [currentWordContext, hasVocabulary]);

    // Check if dictionary is enabled for this language
    const dictionaryEnabled = dictionarySettings.enabled && supports(originalLanguage);

    // Determine source-first rendering
    const sourceFirst = isSourceFirst(subtitleMode);

    return (
        <div
            ref={containerRef}
            className="h-full bg-background rounded-lg border border-border relative"
        >
            <Virtuoso
                ref={virtuosoRef}
                style={{ height: "100%" }}
                totalCount={rows.length}
                overscan={30}
                itemContent={(index) => {
                    const row = rows[index];
                    const isActive = index === activeIndex;

                    return (
                        <div
                            onClick={() => onSeek(row.startTime)}
                            className={cn(
                                "p-3 rounded-lg cursor-pointer transition-all duration-200 group relative mx-2 mb-2",
                                isActive
                                    ? "bg-blue-100 dark:bg-blue-900/40 border-l-4 border-blue-500 shadow-sm"
                                    : "hover:bg-muted text-muted-foreground"
                            )}
                        >
                            <div className="flex justify-between text-xs text-gray-400 mb-1">
                                <span>{formatTime(row.startTime)}</span>
                                <div className="flex items-center gap-1">
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            onAddToAsk({
                                                type: "subtitle",
                                                id: `subtitle-${row.id}`,
                                                text: row.sourceText || row.targetText || "",
                                                startTime: row.startTime,
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
                                                const text = row.sourceText || row.targetText || "";
                                                const snippet = `- [${formatTime(row.startTime)}] ${text}`;
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

                            {/* Render source and target based on mode */}
                            <div
                                className={cn(
                                    "text-sm leading-relaxed whitespace-pre-wrap pr-6",
                                    isActive
                                        ? "text-gray-900 dark:text-gray-100 font-medium"
                                        : ""
                                )}
                            >
                                {sourceFirst ? (
                                    <>
                                        {row.sourceText && (
                                            <HoverableSubtitleText
                                                text={row.sourceText}
                                                locale={originalLanguage}
                                                interactive={dictionaryEnabled}
                                                interactionMode={dictionarySettings.interactionMode}
                                                videoId={videoId}
                                                timestamp={row.startTime}
                                                onWordHover={handleWordHover}
                                                onWordLeave={handleWordLeave}
                                            />
                                        )}
                                        {row.targetText && (
                                            <div className="text-muted-foreground mt-1">
                                                {row.targetText}
                                            </div>
                                        )}
                                    </>
                                ) : (
                                    <>
                                        {row.targetText && (
                                            <div>{row.targetText}</div>
                                        )}
                                        {row.sourceText && (
                                            <div className="text-muted-foreground mt-1">
                                                <HoverableSubtitleText
                                                    text={row.sourceText}
                                                    locale={originalLanguage}
                                                    interactive={dictionaryEnabled}
                                                    interactionMode={dictionarySettings.interactionMode}
                                                    videoId={videoId}
                                                    timestamp={row.startTime}
                                                    onWordHover={handleWordHover}
                                                    onWordLeave={handleWordLeave}
                                                />
                                            </div>
                                        )}
                                    </>
                                )}
                            </div>
                        </div>
                    );
                }}
            />

            {/* Dictionary popup */}
            <DictionaryPopup
                anchorRect={popupAnchor}
                entry={entry}
                loading={lookupLoading}
                error={lookupError}
                isSaved={isCurrentWordSaved}
                onSave={handleSaveVocabulary}
                onClose={handlePopupClose}
            />
        </div>
    );
}

export const SubtitleList = memo(SubtitleListBase);

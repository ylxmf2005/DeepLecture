"use client";

/**
 * HoverableSubtitleText
 *
 * Renders subtitle text with individual word spans that respond to hover.
 * When a word is hovered, it triggers a dictionary lookup.
 */

import { memo, useCallback, useState, useMemo } from "react";
import { tokenizeText, type Token } from "@/lib/dictionary/tokenize";
import { cn } from "@/lib/utils";
import type { DictionaryInteractionMode } from "@/stores/types";

export interface WordContext {
    word: string;
    locale: string;
    sentence: string;
    videoId: string;
    timestamp: number;
}

interface HoverableSubtitleTextProps {
    /** The subtitle text to render */
    text: string;
    /** The locale/language code (e.g., "en", "en-US") */
    locale: string;
    /** Whether hover interactions are enabled */
    interactive?: boolean;
    /** Interaction mode: hover triggers on mouse enter, click triggers on click */
    interactionMode?: DictionaryInteractionMode;
    /** Additional CSS classes for the container */
    className?: string;
    /** Video ID for context */
    videoId?: string;
    /** Timestamp for context */
    timestamp?: number;
    /** Called when a word is hovered */
    onWordHover?: (
        word: string,
        locale: string,
        rect: DOMRect,
        context: WordContext
    ) => void;
    /** Called when hover ends */
    onWordLeave?: () => void;
}

/**
 * Render tokenized text with hoverable word spans
 */
function HoverableSubtitleTextBase({
    text,
    locale,
    interactive = true,
    interactionMode = "hover",
    className,
    videoId = "",
    timestamp = 0,
    onWordHover,
    onWordLeave,
}: HoverableSubtitleTextProps) {
    const [activeIndex, setActiveIndex] = useState<number | null>(null);

    // Memoize tokenization
    const tokens = useMemo(() => tokenizeText(text, locale), [text, locale]);

    const triggerWordLookup = useCallback(
        (token: Token, index: number, event: React.MouseEvent<HTMLSpanElement>) => {
            if (!interactive || !token.isWord || !onWordHover) {
                return;
            }

            setActiveIndex(index);

            const target = event.currentTarget;
            const rect = target.getBoundingClientRect();

            onWordHover(token.text, locale, rect, {
                word: token.text,
                locale,
                sentence: text,
                videoId,
                timestamp,
            });
        },
        [interactive, locale, text, videoId, timestamp, onWordHover]
    );

    const handleMouseEnter = useCallback(
        (token: Token, index: number, event: React.MouseEvent<HTMLSpanElement>) => {
            if (interactionMode !== "hover") return;
            triggerWordLookup(token, index, event);
        },
        [interactionMode, triggerWordLookup]
    );

    const handleClick = useCallback(
        (token: Token, index: number, event: React.MouseEvent<HTMLSpanElement>) => {
            if (interactionMode !== "click") return;
            // Prevent parent click handlers (e.g., subtitle row seek)
            event.stopPropagation();
            triggerWordLookup(token, index, event);
        },
        [interactionMode, triggerWordLookup]
    );

    const handleMouseLeave = useCallback(() => {
        setActiveIndex(null);
        onWordLeave?.();
    }, [onWordLeave]);

    // If not interactive, just render plain text
    if (!interactive) {
        return <span className={className}>{text}</span>;
    }

    return (
        <span className={cn("inline", className)}>
            {tokens.map((token, index) => {
                if (!token.isWord) {
                    // Non-word tokens (whitespace, punctuation) - render as-is
                    return (
                        <span key={index} className="select-text">
                            {token.text}
                        </span>
                    );
                }

                // Word tokens - make hoverable/clickable
                const isActive = activeIndex === index;

                return (
                    <span
                        key={index}
                        onMouseEnter={(e) => handleMouseEnter(token, index, e)}
                        onMouseLeave={handleMouseLeave}
                        onClick={(e) => handleClick(token, index, e)}
                        className={cn(
                            "cursor-pointer select-text transition-colors duration-150",
                            "hover:text-blue-600 dark:hover:text-blue-400",
                            "hover:underline hover:decoration-dotted",
                            isActive && "text-blue-600 dark:text-blue-400 underline decoration-dotted"
                        )}
                    >
                        {token.text}
                    </span>
                );
            })}
        </span>
    );
}

export const HoverableSubtitleText = memo(HoverableSubtitleTextBase);

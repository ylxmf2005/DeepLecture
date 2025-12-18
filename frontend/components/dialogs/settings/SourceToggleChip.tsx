"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Subtitles, Presentation, type LucideIcon } from "lucide-react";
import type { NoteContextMode } from "@/stores/types";

interface SourceOption {
    id: "subtitles" | "slides";
    label: string;
    icon: LucideIcon;
    available: boolean;
}

interface SourceToggleChipProps {
    contextMode: NoteContextMode;
    onChange: (mode: NoteContextMode) => void;
    hasSubtitles: boolean;
    hasSlides: boolean;
}

function deriveSelectedFromMode(mode: NoteContextMode): Set<string> {
    switch (mode) {
        case "subtitle":
            return new Set(["subtitles"]);
        case "slide":
            return new Set(["slides"]);
        case "both":
        default:
            return new Set(["subtitles", "slides"]);
    }
}

function deriveModeFromSelected(selected: Set<string>): NoteContextMode | null {
    const hasSubtitles = selected.has("subtitles");
    const hasSlides = selected.has("slides");

    if (hasSubtitles && hasSlides) return "both";
    if (hasSubtitles) return "subtitle";
    if (hasSlides) return "slide";
    return null; // At least one must be selected
}

export function SourceToggleChip({
    contextMode,
    onChange,
    hasSubtitles,
    hasSlides,
}: SourceToggleChipProps) {
    const selected = deriveSelectedFromMode(contextMode);

    const sources: SourceOption[] = [
        { id: "subtitles", label: "Subtitles", icon: Subtitles, available: hasSubtitles },
        { id: "slides", label: "Slides", icon: Presentation, available: hasSlides },
    ];

    const toggleSource = (sourceId: "subtitles" | "slides", available: boolean) => {
        if (!available) return;

        const newSelected = new Set(selected);
        if (newSelected.has(sourceId)) {
            // Prevent deselecting if it's the only selected source
            if (newSelected.size <= 1) return;
            newSelected.delete(sourceId);
        } else {
            newSelected.add(sourceId);
        }

        const newMode = deriveModeFromSelected(newSelected);
        if (newMode) onChange(newMode);
    };

    return (
        <div className="flex flex-wrap gap-2">
            {sources.map((source) => {
                const isSelected = selected.has(source.id);
                const Icon = source.icon;

                // Only show as selected if both selected AND available
                const showAsSelected = isSelected && source.available;

                return (
                    <motion.button
                        key={source.id}
                        type="button"
                        onClick={() => toggleSource(source.id, source.available)}
                        disabled={!source.available}
                        initial={false}
                        animate={{
                            backgroundColor: showAsSelected
                                ? "rgb(16, 185, 129)"
                                : source.available
                                    ? "rgb(255, 255, 255)"
                                    : "rgb(243, 244, 246)",
                            borderColor: showAsSelected
                                ? "rgb(5, 150, 105)"
                                : source.available
                                    ? "rgb(209, 213, 219)"
                                    : "rgb(229, 231, 235)",
                            color: showAsSelected
                                ? "#fff"
                                : source.available
                                    ? "rgb(31, 41, 55)"
                                    : "rgb(156, 163, 175)",
                        }}
                        whileHover={source.available ? { scale: 1.02 } : {}}
                        whileTap={source.available ? { scale: 0.98 } : {}}
                        transition={{ duration: 0.15 }}
                        className={`relative flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border-2 transition-shadow ${
                            source.available
                                ? "cursor-pointer hover:shadow-md"
                                : "cursor-not-allowed opacity-60"
                        } dark:bg-gray-800 dark:border-gray-600`}
                        style={{
                            backgroundColor: isSelected
                                ? undefined
                                : source.available
                                    ? undefined
                                    : undefined,
                        }}
                    >
                        <motion.div
                            animate={{ scale: showAsSelected ? 1.1 : 1 }}
                            transition={{ duration: 0.15 }}
                        >
                            <Icon className="w-4 h-4" />
                        </motion.div>
                        <span>{source.label}</span>
                        <AnimatePresence>
                            {showAsSelected && (
                                <motion.span
                                    initial={{ scale: 0, opacity: 0, width: 0 }}
                                    animate={{ scale: 1, opacity: 1, width: 16 }}
                                    exit={{ scale: 0, opacity: 0, width: 0 }}
                                    transition={{ type: "spring", stiffness: 500, damping: 25 }}
                                    className="flex items-center"
                                >
                                    <svg width="16" height="16" viewBox="0 0 20 20" fill="none">
                                        <motion.path
                                            d="M5 10.5L9 14.5L15 7.5"
                                            stroke="currentColor"
                                            strokeWidth="2.5"
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            initial={{ pathLength: 0 }}
                                            animate={{ pathLength: 1 }}
                                            transition={{ duration: 0.25 }}
                                        />
                                    </svg>
                                </motion.span>
                            )}
                        </AnimatePresence>
                        {!source.available && (
                            <span className="ml-1 text-xs opacity-70">(N/A)</span>
                        )}
                    </motion.button>
                );
            })}
        </div>
    );
}

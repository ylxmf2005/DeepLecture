import { useEffect, useRef, useState, useCallback } from "react";
import dynamic from "next/dynamic";
import { formatTime, formatDuration } from "@/lib/timeFormat";
import { VideoPlayerRef } from "@/components/video/VideoPlayer";
import { Subtitle } from "@/lib/srt";
import { summarizeContext, TimelineEntry } from "@/lib/api";
import type { AskContextItem } from "@/lib/askTypes";
import type { SubtitleDisplayMode } from "@/stores/types";
import {
    getAutoSwitchModeOnHide,
    getAutoSwitchModeOnShow,
    createAutoSwitchState,
    updateStateOnAutoSwitch,
    resetAutoSwitchState,
    type AutoSwitchState,
} from "@/lib/subtitleAutoSwitch";
import { logger } from "@/shared/infrastructure";

const log = logger.scope("FocusModeHandler");

/** Debounce delay before auto-switching subtitles to avoid false triggers from brief tab switches */
const AUTO_SWITCH_DEBOUNCE_MS = 1500;

const MissedContentDialog = dynamic(
    () => import("@/components/dialogs/MissedContentDialog").then((mod) => mod.MissedContentDialog),
    { ssr: false }
);

interface FocusModeHandlerProps {
    playerRef: React.RefObject<VideoPlayerRef | null>;
    subtitles: Subtitle[];
    currentTime: number;
    learnerProfile?: string;
    // Settings
    autoPauseOnLeave: boolean;
    autoResumeOnReturn: boolean;
    autoSwitchSubtitlesOnLeave: boolean;
    subtitleMode: SubtitleDisplayMode;
    hasTranslation: boolean;
    onSubtitleModeChange: (mode: SubtitleDisplayMode) => void;
    summaryThresholdSeconds: number; // e.g. 60
    // Smart Skip settings
    skipRamblingEnabled: boolean;
    timelineEntries: TimelineEntry[];
    onAddToAsk: (item: AskContextItem) => void;
    onAddToNotes: (markdown: string) => void;
}

export function FocusModeHandler({
    playerRef,
    subtitles,
    currentTime,
    learnerProfile,
    autoPauseOnLeave,
    autoResumeOnReturn,
    autoSwitchSubtitlesOnLeave,
    subtitleMode,
    hasTranslation,
    onSubtitleModeChange,
    summaryThresholdSeconds,
    skipRamblingEnabled,
    timelineEntries,
    onAddToAsk,
    onAddToNotes,
}: FocusModeHandlerProps) {
    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [summary, setSummary] = useState("");
    const [missedDurationStr, setMissedDurationStr] = useState("");
    const [jumpBackTime, setJumpBackTime] = useState<number | null>(null);
    const [missedStartTime, setMissedStartTime] = useState<number | null>(null);
    const [missedEndTime, setMissedEndTime] = useState<number | null>(null);
    const [isSummaryLoading, setIsSummaryLoading] = useState(false);

    const leaveTimeRef = useRef<number | null>(null);
    const wasPlayingRef = useRef(false);
    const autoSwitchStateRef = useRef<AutoSwitchState>(createAutoSwitchState());
    const hideDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Compute the amount of "kept" content between two timestamps,
    // excluding gaps that Smart Skip would jump over.
    const computeMissedSeconds = useCallback(
        (start: number, end: number): number => {
            const windowStart = Math.min(start, end);
            const windowEnd = Math.max(start, end);
            const raw = windowEnd - windowStart;

            if (!skipRamblingEnabled || timelineEntries.length === 0 || raw <= 0) {
                return Math.max(raw, 0);
            }

            let kept = 0;
            for (const entry of timelineEntries) {
                const overlapStart = Math.max(windowStart, entry.start);
                const overlapEnd = Math.min(windowEnd, entry.end);
                if (overlapEnd > overlapStart) {
                    kept += overlapEnd - overlapStart;
                }
            }

            return kept;
        },
        [skipRamblingEnabled, timelineEntries]
    );

    const handleVisibilityChange = useCallback(async () => {
        if (document.hidden) {
            const isPlaying = playerRef.current?.isPlaying() || false;
            wasPlayingRef.current = isPlaying;
            leaveTimeRef.current = currentTime;

            // Clear any existing debounce timer
            if (hideDebounceRef.current) {
                clearTimeout(hideDebounceRef.current);
                hideDebounceRef.current = null;
            }

            // Handle auto-switch subtitles with debounce (1.5s delay to avoid brief tab switches)
            if (autoSwitchSubtitlesOnLeave) {
                hideDebounceRef.current = setTimeout(() => {
                    const newMode = getAutoSwitchModeOnHide({
                        enabled: autoSwitchSubtitlesOnLeave,
                        hasTranslation,
                        currentMode: subtitleMode,
                    });

                    if (newMode !== null) {
                        autoSwitchStateRef.current = updateStateOnAutoSwitch(subtitleMode);
                        onSubtitleModeChange(newMode);
                    }
                }, AUTO_SWITCH_DEBOUNCE_MS);
            }

            if (isPlaying && autoPauseOnLeave) {
                playerRef.current?.pause();
            }
        } else {
            // Clear debounce timer if returning quickly
            if (hideDebounceRef.current) {
                clearTimeout(hideDebounceRef.current);
                hideDebounceRef.current = null;
            }

            // Handle auto-switch subtitle restore
            if (autoSwitchSubtitlesOnLeave) {
                const restoreMode = getAutoSwitchModeOnShow({
                    enabled: autoSwitchSubtitlesOnLeave,
                    hasTranslation,
                    currentMode: subtitleMode,
                    state: autoSwitchStateRef.current,
                });

                if (restoreMode !== null) {
                    onSubtitleModeChange(restoreMode);
                }
                autoSwitchStateRef.current = resetAutoSwitchState();
            }

            const leaveTimestamp = leaveTimeRef.current;

            if (autoPauseOnLeave) {
                if (wasPlayingRef.current && autoResumeOnReturn) {
                    playerRef.current?.play();
                }
                leaveTimeRef.current = null;
                return;
            }

            const currentVideoTime = playerRef.current?.getCurrentTime() || currentTime;

            if (leaveTimestamp !== null && wasPlayingRef.current) {
                const missedSeconds = computeMissedSeconds(leaveTimestamp, currentVideoTime);

                if (missedSeconds > summaryThresholdSeconds) {
                    playerRef.current?.pause();
                    setJumpBackTime(leaveTimestamp);
                    setMissedStartTime(leaveTimestamp);
                    setMissedEndTime(currentVideoTime);
                    setMissedDurationStr(formatDuration(missedSeconds));
                    setIsDialogOpen(true);
                    setSummary("");
                    setIsSummaryLoading(false);
                }
            }

            leaveTimeRef.current = null;
        }
    }, [
        autoPauseOnLeave,
        autoResumeOnReturn,
        autoSwitchSubtitlesOnLeave,
        subtitleMode,
        hasTranslation,
        onSubtitleModeChange,
        summaryThresholdSeconds,
        currentTime,
        playerRef,
        computeMissedSeconds,
    ]);

    useEffect(() => {
        document.addEventListener("visibilitychange", handleVisibilityChange);
        return () => {
            document.removeEventListener("visibilitychange", handleVisibilityChange);
            // Clear pending debounce timeout on unmount to prevent memory leak
            // and avoid calling onSubtitleModeChange on unmounted component
            if (hideDebounceRef.current) {
                clearTimeout(hideDebounceRef.current);
                hideDebounceRef.current = null;
            }
        };
    }, [handleVisibilityChange]);

    const handleGenerateSummary = async () => {
        if (missedStartTime === null || missedEndTime === null || isSummaryLoading) {
            return;
        }

        setIsSummaryLoading(true);
        setSummary("");

        // Find missed subtitles (only within kept segments when Smart Skip is enabled).
        const missedSubs = subtitles.filter((s) => {
            if (s.endTime < missedStartTime || s.startTime > missedEndTime) {
                return false;
            }

            const subWindowStart = Math.max(s.startTime, missedStartTime);
            const subWindowEnd = Math.min(s.endTime, missedEndTime);
            if (subWindowEnd <= subWindowStart) {
                return false;
            }

            if (!skipRamblingEnabled || timelineEntries.length === 0) {
                return true;
            }

            // Only include subtitle text that falls inside kept
            // timeline entries when Smart Skip is enabled.
            for (const entry of timelineEntries) {
                const overlapStart = Math.max(subWindowStart, entry.start);
                const overlapEnd = Math.min(subWindowEnd, entry.end);
                if (overlapEnd > overlapStart) {
                    return true;
                }
            }

            return false;
        });

        if (missedSubs.length === 0) {
            setSummary("No subtitles were found for the missed segment, so a summary could not be generated.");
            setIsSummaryLoading(false);
            return;
        }

        try {
            const context = missedSubs.map((s) => ({
                type: "subtitle" as const,
                id: s.id,
                text: s.text,
                startTime: s.startTime,
                endTime: s.endTime,
            }));

            const result = await summarizeContext({
                context,
                learnerProfile,
            });

            setSummary(result.summary);
            setIsSummaryLoading(false);
        } catch (e) {
            log.error("Failed to generate summary", e instanceof Error ? e : new Error(String(e)));
            setSummary("Sorry, we could not generate a summary for this segment.");
            setIsSummaryLoading(false);
        }
    };

    const handleJumpBack = () => {
        if (jumpBackTime !== null) {
            playerRef.current?.seekTo(jumpBackTime);
            playerRef.current?.play();
        }
        setIsDialogOpen(false);
    };

    const handleAskAboutMissed = () => {
        if (!summary || missedStartTime === null) {
            return;
        }

        const item: AskContextItem = {
            type: "subtitle",
            id: `missed-${missedStartTime.toFixed(1)}`,
            text: summary,
            startTime: missedStartTime,
        };

        onAddToAsk(item);
        setIsDialogOpen(false);
    };

    const handleAddMissedToNotes = () => {
        if (!summary) {
            return;
        }

        let heading = "### Missed segment";
        if (missedStartTime !== null && missedEndTime !== null) {
            heading += ` (${formatTime(missedStartTime)} - ${formatTime(missedEndTime)})`;
        }

        const snippet = `${heading}\n\n${summary}`.trim();
            onAddToNotes(snippet);
        setIsDialogOpen(false);
    };

    const handleClose = () => {
        setIsDialogOpen(false);
        // "Just close" -> implies continue playing from where we are
        playerRef.current?.play();
    };

    return (
        <MissedContentDialog
            isOpen={isDialogOpen}
            onClose={handleClose}
            onJumpBack={handleJumpBack}
            onGenerateSummary={handleGenerateSummary}
            summary={summary}
            missedDuration={missedDurationStr}
            isLoading={isSummaryLoading}
            onAsk={handleAskAboutMissed}
            onAddToNotes={handleAddMissedToNotes}
        />
    );
}

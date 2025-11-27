import { useEffect, useRef, useState, useCallback } from "react";
import { formatTime, formatDuration } from "@/lib/timeFormat";
import { VideoPlayerRef } from "@/components/VideoPlayer";
import { Subtitle } from "@/lib/srt";
import { summarizeContext, TimelineEntry } from "@/lib/api";
import { MissedContentDialog } from "@/components/MissedContentDialog";
import type { AskContextItem } from "@/lib/askTypes";

interface FocusModeHandlerProps {
    playerRef: React.RefObject<VideoPlayerRef | null>;
    subtitles: Subtitle[];
    currentTime: number;
    learnerProfile?: string;
    // Settings
    autoPauseOnLeave: boolean;
    autoResumeOnReturn: boolean;
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
            // User left
            const isPlaying = playerRef.current?.isPlaying() || false;
            wasPlayingRef.current = isPlaying;
            leaveTimeRef.current = currentTime;

            if (isPlaying && autoPauseOnLeave) {
                playerRef.current?.pause();
            }
        } else {
            // User returned
            const leaveTimestamp = leaveTimeRef.current;

            // If we don't have a valid leave timestamp, just return.
            // Product requirement (translated from the original notes):
            // "Record how many seconds pass between when the user leaves and comes back.
            // If this exceeds a certain threshold, summarize what the instructor covered
            // during that time."
            // If the video was PAUSED, the learner didn't miss anything; if it kept
            // PLAYING, they missed content. So we care about the VIDEO TIME difference
            // while it was playing.
            // This leads to two cases:
            // Case 1: Auto-pause ON  -> no missed content.
            // Case 2: Auto-pause OFF -> video keeps playing -> missed content.
            // We only trigger a summary in Case 2 when the video was playing.

            if (autoPauseOnLeave) {
                // Case 1: Auto-paused. Just resume if configured.
                if (wasPlayingRef.current && autoResumeOnReturn) {
                    playerRef.current?.play();
                }
                leaveTimeRef.current = null;
                return;
            }

            // Case 2: Did not auto-pause. Check if we missed enough content.
            // We need to know the current video time vs leave video time.
            // But `currentTime` prop might not be updated immediately upon visibility change if the component didn't re-render.
            // Better to ask player for current time.
            const currentVideoTime = playerRef.current?.getCurrentTime() || currentTime;

            if (leaveTimestamp !== null && wasPlayingRef.current) {
                const missedSeconds = computeMissedSeconds(leaveTimestamp, currentVideoTime);

                if (missedSeconds > summaryThresholdSeconds) {
                    // Pause and show dialog, but do NOT auto-generate summary.
                    // Let the user decide whether to rewind, generate a summary, or continue.
                    playerRef.current?.pause(); // Pause to show dialog
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
        summaryThresholdSeconds,
        currentTime,
        playerRef,
        computeMissedSeconds,
    ]);

    useEffect(() => {
        document.addEventListener("visibilitychange", handleVisibilityChange);
        return () => {
            document.removeEventListener("visibilitychange", handleVisibilityChange);
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
            console.error("Failed to generate summary", e);
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

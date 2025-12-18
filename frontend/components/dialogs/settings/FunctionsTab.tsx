"use client";

import { ListVideo, MessageSquare, FileText } from "lucide-react";
import { useShallow } from "zustand/react/shallow";
import { useGlobalSettingsStore, useNoteSettings } from "@/stores/useGlobalSettingsStore";
import { useVideoStateStore } from "@/stores/useVideoStateStore";
import { SettingsSection, SettingsCard, SettingsRow } from "./SettingsSection";
import { ToggleSwitch } from "./ToggleSwitch";
import { SourceToggleChip } from "./SourceToggleChip";
import type { SettingsTabProps } from "./types";

export function FunctionsTab({ video }: SettingsTabProps) {
    const playback = useGlobalSettingsStore(useShallow((state) => state.playback));
    const noteSettings = useNoteSettings();
    const setNoteContextMode = useGlobalSettingsStore((s) => s.setNoteContextMode);

    const setSubtitleContextWindowSeconds = useGlobalSettingsStore((s) => s.setSubtitleContextWindowSeconds);
    const setSubtitleRepeatCount = useGlobalSettingsStore((s) => s.setSubtitleRepeatCount);

    const skipRamblingEnabled = useVideoStateStore(
        (state) => state.videos[video.id]?.smartSkipEnabled ?? false
    );
    const toggleSmartSkip = useVideoStateStore((state) => state.toggleSmartSkip);

    const hasSubtitles = video.subtitleStatus === "ready";
    const hasSlides = video.type === "slide" || Boolean(video.pageCount && video.pageCount > 0);

    return (
        <>
            {/* Timeline Section */}
            <SettingsSection icon={ListVideo} title="Timeline" accentColor="amber">
                <SettingsCard>
                    <SettingsRow
                        label="Smart Skip"
                        description="Automatically skip rambling parts"
                    >
                        <ToggleSwitch
                            enabled={skipRamblingEnabled}
                            onChange={() => toggleSmartSkip(video.id)}
                            disabled={video?.subtitleStatus !== "ready"}
                            accentColor="amber"
                        />
                    </SettingsRow>
                </SettingsCard>
            </SettingsSection>

            {/* Ask AI Section */}
            <SettingsSection icon={MessageSquare} title="Ask AI" accentColor="purple">
                <SettingsCard>
                    <div className="space-y-3">
                        <div className="flex items-baseline justify-between gap-4">
                            <span className="font-medium text-gray-900 dark:text-gray-100">
                                Subtitle Context Window
                            </span>
                            <span className="text-sm font-semibold text-purple-600 dark:text-purple-400 whitespace-nowrap">
                                ±{playback.subtitleContextWindowSeconds} seconds
                            </span>
                        </div>
                        <input
                            type="range"
                            min="5"
                            max="120"
                            step="5"
                            value={playback.subtitleContextWindowSeconds}
                            onChange={(e) => setSubtitleContextWindowSeconds(Number(e.target.value))}
                            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-purple-500"
                        />
                        <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                            Controls how much original-language transcript is included when explaining screenshots or adding video moments to Ask.
                        </p>
                    </div>

                    <div className="space-y-2 pt-3 border-t border-gray-100 dark:border-gray-700">
                        <div className="flex items-baseline justify-between gap-4">
                            <span className="font-medium text-gray-900 dark:text-gray-100">
                                Subtitle Repeat Count
                            </span>
                            <span className="text-sm font-semibold text-purple-600 dark:text-purple-400 whitespace-nowrap">
                                ×{playback.subtitleRepeatCount}
                            </span>
                        </div>
                        <input
                            type="range"
                            min="1"
                            max="5"
                            step="1"
                            value={playback.subtitleRepeatCount}
                            onChange={(e) => setSubtitleRepeatCount(Number(e.target.value))}
                            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-purple-500"
                        />
                        <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                            Controls how many times each subtitle line plays before moving on.
                        </p>
                    </div>
                </SettingsCard>
            </SettingsSection>

            {/* Note Section */}
            <SettingsSection icon={FileText} title="Note Generation" accentColor="emerald">
                <SettingsCard>
                    <div className="space-y-3">
                        <div className="flex items-baseline justify-between gap-4">
                            <span className="font-medium text-gray-900 dark:text-gray-100">
                                Context Sources
                            </span>
                        </div>
                        <SourceToggleChip
                            contextMode={noteSettings.contextMode}
                            onChange={setNoteContextMode}
                            hasSubtitles={hasSubtitles}
                            hasSlides={hasSlides}
                        />
                        <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                            {noteSettings.contextMode === "both"
                                ? "Using both subtitles and slides"
                                : noteSettings.contextMode === "subtitle"
                                    ? "Using only transcript text"
                                    : "Using only slide/PDF content"}
                        </p>
                    </div>
                </SettingsCard>
            </SettingsSection>
        </>
    );
}

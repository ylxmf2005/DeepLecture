"use client";

import { Subtitles, PlayCircle } from "lucide-react";
import { useShallow } from "zustand/react/shallow";
import { useGlobalSettingsStore } from "@/stores/useGlobalSettingsStore";
import { SettingsSection, SettingsCard, SettingsRow } from "./SettingsSection";
import { ToggleSwitch } from "./ToggleSwitch";
import type { SettingsTabProps } from "./types";

export function PlayerTab(_props: SettingsTabProps) {
    const { playback, subtitleDisplay, hideSidebars } = useGlobalSettingsStore(
        useShallow((state) => ({
            playback: state.playback,
            subtitleDisplay: state.subtitleDisplay,
            hideSidebars: state.hideSidebars,
        }))
    );

    const setAutoPauseOnLeave = useGlobalSettingsStore((s) => s.setAutoPauseOnLeave);
    const setAutoResumeOnReturn = useGlobalSettingsStore((s) => s.setAutoResumeOnReturn);
    const setAutoSwitchVoiceoverOnLeave = useGlobalSettingsStore((s) => s.setAutoSwitchVoiceoverOnLeave);
    const setSummaryThresholdSeconds = useGlobalSettingsStore((s) => s.setSummaryThresholdSeconds);
    const setSubtitleRepeatCount = useGlobalSettingsStore((s) => s.setSubtitleRepeatCount);
    const setSubtitleFontSize = useGlobalSettingsStore((s) => s.setSubtitleFontSize);
    const setSubtitleBottomOffset = useGlobalSettingsStore((s) => s.setSubtitleBottomOffset);
    const toggleHideSidebars = useGlobalSettingsStore((s) => s.toggleHideSidebars);

    return (
        <>
            {/* Subtitle Display Section */}
            <SettingsSection icon={Subtitles} title="Subtitle Display" accentColor="violet">
                <SettingsCard>
                    <div className="space-y-2">
                        <div className="flex items-baseline justify-between gap-4">
                            <span className="font-medium text-gray-900 dark:text-gray-100">
                                Subtitle Size
                            </span>
                            <span className="text-sm font-semibold text-violet-600 dark:text-violet-400 whitespace-nowrap">
                                {subtitleDisplay.fontSize}px
                            </span>
                        </div>
                        <input
                            type="range"
                            min={10}
                            max={40}
                            step={1}
                            value={subtitleDisplay.fontSize}
                            onChange={(e) => setSubtitleFontSize(Number(e.target.value))}
                            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-violet-500"
                        />
                        <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                            Adjusts the base subtitle font size for the video player. Fullscreen mode may render slightly larger.
                        </p>
                    </div>

                    <div className="space-y-2 pt-3 border-t border-gray-100 dark:border-gray-700">
                        <div className="flex items-baseline justify-between gap-4">
                            <span className="font-medium text-gray-900 dark:text-gray-100">
                                Vertical Position
                            </span>
                            <span className="text-sm font-semibold text-violet-600 dark:text-violet-400 whitespace-nowrap">
                                {subtitleDisplay.bottomOffset}px from bottom
                            </span>
                        </div>
                        <input
                            type="range"
                            min={0}
                            max={160}
                            step={4}
                            value={subtitleDisplay.bottomOffset}
                            onChange={(e) => setSubtitleBottomOffset(Number(e.target.value))}
                            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-violet-500"
                        />
                        <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                            Moves subtitles up or down so they do not overlap with course content or the player controls.
                        </p>
                    </div>

                    <div className="space-y-2 pt-3 border-t border-gray-100 dark:border-gray-700">
                        <div className="flex items-baseline justify-between gap-4">
                            <span className="font-medium text-gray-900 dark:text-gray-100">
                                Subtitle Repeat Count
                            </span>
                            <span className="text-sm font-semibold text-violet-600 dark:text-violet-400 whitespace-nowrap">
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
                            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-violet-500"
                        />
                        <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                            Controls how many times each subtitle line plays before moving on.
                        </p>
                    </div>
                </SettingsCard>
            </SettingsSection>

            {/* Focus Mode Section */}
            <SettingsSection icon={PlayCircle} title="Focus Mode" accentColor="rose">
                <SettingsCard>
                    <SettingsRow
                        label="Auto-pause on Leave"
                        description="Pause video when you switch tabs"
                    >
                        <ToggleSwitch
                            enabled={playback.autoPauseOnLeave}
                            onChange={() => setAutoPauseOnLeave(!playback.autoPauseOnLeave)}
                            accentColor="rose"
                        />
                    </SettingsRow>

                    <SettingsRow
                        label="Auto-resume on Return"
                        description="Resume video when you return"
                    >
                        <ToggleSwitch
                            enabled={playback.autoResumeOnReturn}
                            onChange={() => setAutoResumeOnReturn(!playback.autoResumeOnReturn)}
                            disabled={!playback.autoPauseOnLeave}
                            accentColor="rose"
                        />
                    </SettingsRow>

                    <SettingsRow
                        label="Auto-switch Voiceover"
                        description="Switch to translated voiceover when you leave, restore on return"
                    >
                        <ToggleSwitch
                            enabled={playback.autoSwitchVoiceoverOnLeave}
                            onChange={() => setAutoSwitchVoiceoverOnLeave(!playback.autoSwitchVoiceoverOnLeave)}
                            accentColor="rose"
                        />
                    </SettingsRow>

                    <div className="space-y-2 pt-2 border-t border-gray-100 dark:border-gray-700">
                        <div className="flex items-center justify-between">
                            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Summary Threshold</span>
                            <span className="text-xs text-gray-500 dark:text-gray-400">{playback.summaryThresholdSeconds} seconds</span>
                        </div>
                        <input
                            type="range"
                            min="10"
                            max="300"
                            step="10"
                            value={playback.summaryThresholdSeconds}
                            onChange={(e) => setSummaryThresholdSeconds(Number(e.target.value))}
                            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-rose-500"
                        />
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                            Show summary if you missed more than this amount of content.
                        </p>
                    </div>

                    <SettingsRow
                        label="Immersive Mode"
                        description="Hide sidebars to focus on the video"
                        withBorder
                    >
                        <ToggleSwitch
                            enabled={hideSidebars}
                            onChange={toggleHideSidebars}
                            accentColor="rose"
                        />
                    </SettingsRow>
                </SettingsCard>
            </SettingsSection>
        </>
    );
}

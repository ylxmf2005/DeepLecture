"use client";

import { Subtitles, PlayCircle } from "lucide-react";
import { SettingsSection, SettingsCard, SettingsRow } from "./SettingsSection";
import { ToggleSwitch } from "./ToggleSwitch";
import { ScopeAwareField } from "./ScopeAwareField";
import type { SettingsTabProps } from "./types";

export function PlayerTab({ scope, settings }: SettingsTabProps) {
    const isVideoScope = scope === "video";
    const { values, isOverridden, clearField } = settings;
    const { playback, subtitleDisplay, hideSidebars } = values;

    return (
        <>
            {/* Subtitle Display Section */}
            <SettingsSection icon={Subtitles} title="Subtitle Display" accentColor="violet">
                <SettingsCard>
                    <ScopeAwareField path="subtitleDisplay.fontSize" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
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
                                onChange={(e) => settings.setSubtitleFontSize(Number(e.target.value))}
                                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-violet-500"
                            />
                            <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                                Adjusts the base subtitle font size for the video player. Fullscreen mode may render slightly larger.
                            </p>
                        </div>
                    </ScopeAwareField>

                    <ScopeAwareField path="subtitleDisplay.bottomOffset" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
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
                                onChange={(e) => settings.setSubtitleBottomOffset(Number(e.target.value))}
                                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-violet-500"
                            />
                            <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                                Moves subtitles up or down so they do not overlap with course content or the player controls.
                            </p>
                        </div>
                    </ScopeAwareField>

                    <ScopeAwareField path="playback.subtitleRepeatCount" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
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
                                onChange={(e) => settings.setSubtitleRepeatCount(Number(e.target.value))}
                                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-violet-500"
                            />
                            <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                                Controls how many times each subtitle line plays before moving on.
                            </p>
                        </div>
                    </ScopeAwareField>
                </SettingsCard>
            </SettingsSection>

            {/* Focus Mode Section */}
            <SettingsSection icon={PlayCircle} title="Focus Mode" accentColor="rose">
                <SettingsCard>
                    <ScopeAwareField path="playback.autoPauseOnLeave" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                        <SettingsRow
                            label="Auto-pause on Leave"
                            description="Pause video when you switch tabs"
                        >
                            <ToggleSwitch
                                enabled={playback.autoPauseOnLeave}
                                onChange={() => settings.setAutoPauseOnLeave(!playback.autoPauseOnLeave)}
                                accentColor="rose"
                            />
                        </SettingsRow>
                    </ScopeAwareField>

                    <ScopeAwareField path="playback.autoResumeOnReturn" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                        <SettingsRow
                            label="Auto-resume on Return"
                            description="Resume video when you return"
                        >
                            <ToggleSwitch
                                enabled={playback.autoResumeOnReturn}
                                onChange={() => settings.setAutoResumeOnReturn(!playback.autoResumeOnReturn)}
                                disabled={!playback.autoPauseOnLeave}
                                accentColor="rose"
                            />
                        </SettingsRow>
                    </ScopeAwareField>

                    <ScopeAwareField path="playback.autoSwitchVoiceoverOnLeave" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                        <SettingsRow
                            label="Auto-switch Voiceover"
                            description="Switch to translated voiceover when you leave, restore on return"
                        >
                            <ToggleSwitch
                                enabled={playback.autoSwitchVoiceoverOnLeave}
                                onChange={() => settings.setAutoSwitchVoiceoverOnLeave(!playback.autoSwitchVoiceoverOnLeave)}
                                accentColor="rose"
                            />
                        </SettingsRow>
                    </ScopeAwareField>

                    <ScopeAwareField path="playback.voiceoverAutoSwitchThresholdMs" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                        <div className="space-y-2 pt-2 border-t border-gray-100 dark:border-gray-700">
                            <div className="flex items-center justify-between">
                                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Voiceover Switch Threshold</span>
                                <span className="text-xs text-gray-500 dark:text-gray-400">{(playback.voiceoverAutoSwitchThresholdMs / 1000).toFixed(1)} seconds</span>
                            </div>
                            <input
                                type="range"
                                min="0"
                                max="5000"
                                step="100"
                                value={playback.voiceoverAutoSwitchThresholdMs}
                                onChange={(e) => settings.setVoiceoverAutoSwitchThresholdMs(Number(e.target.value))}
                                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-rose-500"
                            />
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                Only switch voiceover if you stay away longer than this threshold.
                            </p>
                        </div>
                    </ScopeAwareField>

                    <ScopeAwareField path="playback.summaryThresholdSeconds" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
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
                                onChange={(e) => settings.setSummaryThresholdSeconds(Number(e.target.value))}
                                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-rose-500"
                            />
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                Show summary if you missed more than this amount of content.
                            </p>
                        </div>
                    </ScopeAwareField>

                    <ScopeAwareField path="hideSidebars" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                        <SettingsRow
                            label="Immersive Mode"
                            description="Hide sidebars to focus on the video"
                            withBorder
                        >
                            <ToggleSwitch
                                enabled={hideSidebars}
                                onChange={settings.toggleHideSidebars}
                                accentColor="rose"
                            />
                        </SettingsRow>
                    </ScopeAwareField>
                </SettingsCard>
            </SettingsSection>
        </>
    );
}

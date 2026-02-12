"use client";

import { ListVideo, MessageSquare, FileText, BookOpen } from "lucide-react";
import { useVideoStateStore } from "@/stores/useVideoStateStore";
import { SettingsSection, SettingsCard, SettingsRow } from "./SettingsSection";
import { ToggleSwitch } from "./ToggleSwitch";
import { SourceToggleChip } from "./SourceToggleChip";
import { ScopeAwareField } from "./ScopeAwareField";
import type { SettingsTabProps } from "./types";

export function FunctionsTab({ video, scope, settings }: SettingsTabProps) {
    const isVideoScope = scope === "video";
    const { values, isOverridden, clearField } = settings;
    const { playback, note: noteSettings, dictionary: dictionarySettings } = values;

    const skipRamblingEnabled = useVideoStateStore(
        (state) => video ? (state.videos[video.id]?.smartSkipEnabled ?? false) : false
    );
    const toggleSmartSkip = useVideoStateStore((state) => state.toggleSmartSkip);

    const hasSubtitles = video ? video.subtitleStatus === "ready" : false;
    const hasSlides = video ? (video.type === "slide" || Boolean(video.pageCount && video.pageCount > 0)) : false;

    return (
        <>
            {/* Timeline Section */}
            {video && (
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
            )}

            {/* Ask AI Section */}
            <SettingsSection icon={MessageSquare} title="Ask AI" accentColor="purple">
                <SettingsCard>
                    <ScopeAwareField path="playback.subtitleContextWindowSeconds" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
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
                                onChange={(e) => settings.setSubtitleContextWindowSeconds(Number(e.target.value))}
                                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-purple-500"
                            />
                            <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                                Controls how much original-language transcript is included when explaining screenshots or adding video moments to Ask.
                            </p>
                        </div>
                    </ScopeAwareField>

                    <ScopeAwareField path="playback.subtitleRepeatCount" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
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
                                onChange={(e) => settings.setSubtitleRepeatCount(Number(e.target.value))}
                                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-purple-500"
                            />
                            <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                                Controls how many times each subtitle line plays before moving on.
                            </p>
                        </div>
                    </ScopeAwareField>
                </SettingsCard>
            </SettingsSection>

            {/* Note Section */}
            <SettingsSection icon={FileText} title="Note Generation" accentColor="emerald">
                <SettingsCard>
                    <ScopeAwareField path="note.contextMode" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                        <div className="space-y-3">
                            <div className="flex items-baseline justify-between gap-4">
                                <span className="font-medium text-gray-900 dark:text-gray-100">
                                    Context Sources
                                </span>
                            </div>
                            <SourceToggleChip
                                contextMode={noteSettings.contextMode}
                                onChange={settings.setNoteContextMode}
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
                    </ScopeAwareField>
                </SettingsCard>
            </SettingsSection>

            {/* Dictionary Section */}
            <SettingsSection icon={BookOpen} title="Dictionary" accentColor="blue">
                <SettingsCard>
                    <ScopeAwareField path="dictionary.enabled" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                        <SettingsRow
                            label="Enable Dictionary"
                            description="Look up word definitions in subtitles"
                        >
                            <ToggleSwitch
                                enabled={dictionarySettings.enabled}
                                onChange={() => settings.setDictionaryEnabled(!dictionarySettings.enabled)}
                                accentColor="blue"
                            />
                        </SettingsRow>
                    </ScopeAwareField>

                    <ScopeAwareField path="dictionary.interactionMode" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                        <div className="space-y-3 pt-3 border-t border-gray-100 dark:border-gray-700">
                            <div className="flex items-baseline justify-between gap-4">
                                <span className="font-medium text-gray-900 dark:text-gray-100">
                                    Interaction Mode
                                </span>
                            </div>
                            <div className="flex gap-2" role="group" aria-label="Interaction mode">
                                <button
                                    type="button"
                                    onClick={() => settings.setDictionaryInteractionMode("hover")}
                                    disabled={!dictionarySettings.enabled}
                                    aria-pressed={dictionarySettings.interactionMode === "hover"}
                                    className={`flex-1 px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
                                        dictionarySettings.interactionMode === "hover"
                                            ? "bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300"
                                            : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
                                    } ${!dictionarySettings.enabled ? "opacity-50 cursor-not-allowed" : ""}`}
                                >
                                    Hover
                                </button>
                                <button
                                    type="button"
                                    onClick={() => settings.setDictionaryInteractionMode("click")}
                                    disabled={!dictionarySettings.enabled}
                                    aria-pressed={dictionarySettings.interactionMode === "click"}
                                    className={`flex-1 px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
                                        dictionarySettings.interactionMode === "click"
                                            ? "bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300"
                                            : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
                                    } ${!dictionarySettings.enabled ? "opacity-50 cursor-not-allowed" : ""}`}
                                >
                                    Click
                                </button>
                            </div>
                            <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                                {dictionarySettings.interactionMode === "hover"
                                    ? "Hover over words to see definitions (auto-trigger)"
                                    : "Click on words to see definitions (click won't seek video)"}
                            </p>
                        </div>
                    </ScopeAwareField>
                </SettingsCard>
            </SettingsSection>
        </>
    );
}

"use client";

import { useState, useEffect } from "react";
import { BrainCircuit, Globe, Sparkles } from "lucide-react";
import { CustomSelect } from "@/components/ui/CustomSelect";
import { WHISPER_LANGUAGES } from "@/lib/languages";
import { SettingsSection, SettingsCard } from "./SettingsSection";
import { ScopeAwareField } from "./ScopeAwareField";
import type { SettingsTabProps } from "./types";

export function GeneralTab({ scope, settings }: SettingsTabProps) {
    const isVideoScope = scope === "video";
    const { values, isOverridden, clearField } = settings;

    const [draftLearnerProfile, setDraftLearnerProfile] = useState(values.learnerProfile);

    useEffect(() => {
        setDraftLearnerProfile(values.learnerProfile);
    }, [values.learnerProfile]);

    return (
        <>
            {/* Learning Preferences Section */}
            <SettingsSection icon={BrainCircuit} title="Learning Preferences" accentColor="blue">
                <SettingsCard>
                    <ScopeAwareField path="learnerProfile" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                        <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                            Customize your AI learning experience. Tell us about your background and goals to get tailored explanations and notes.
                        </p>
                        <div className="relative mt-3">
                            <textarea
                                value={draftLearnerProfile}
                                onChange={(e) => setDraftLearnerProfile(e.target.value)}
                                rows={4}
                                placeholder="e.g. I know basic Python, I am preparing for the final exam, please skip trivial chit-chat and focus on problem-solving steps."
                                className="w-full px-4 py-3 rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 text-sm resize-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all placeholder:text-gray-400"
                            />
                            <div className="absolute bottom-3 right-3">
                                {draftLearnerProfile && (
                                    <span className="text-[10px] text-gray-400 bg-white dark:bg-gray-800 px-2 py-1 rounded-full border border-gray-100 dark:border-gray-700 shadow-sm">
                                        {draftLearnerProfile.length} chars
                                    </span>
                                )}
                            </div>
                        </div>
                        <div className="flex justify-end mt-3">
                            <button
                                type="button"
                                onClick={() => settings.setLearnerProfile(draftLearnerProfile.trim())}
                                className="inline-flex items-center px-4 py-2 rounded-lg bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 transition-colors shadow-sm hover:shadow-md active:scale-95"
                            >
                                <Sparkles className="w-3 h-3 mr-2" />
                                Apply Preferences
                            </button>
                        </div>
                    </ScopeAwareField>
                </SettingsCard>
            </SettingsSection>

            {/* Language Settings Section */}
            <SettingsSection icon={Globe} title="Language Settings" accentColor="emerald">
                <SettingsCard>
                    <div className="space-y-4">
                        <ScopeAwareField path="language.original" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                            <div className="space-y-2">
                                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                                    Source Language
                                </label>
                                <CustomSelect
                                    value={values.language.original}
                                    onChange={settings.setOriginalLanguage}
                                    options={WHISPER_LANGUAGES}
                                    accent="emerald"
                                />
                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                    The language spoken in the video audio.
                                </p>
                            </div>
                        </ScopeAwareField>

                        <ScopeAwareField path="language.translated" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                            <div className="space-y-2">
                                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                                    Target Language
                                </label>
                                <CustomSelect
                                    value={values.language.translated}
                                    onChange={settings.setTranslatedLanguage}
                                    options={WHISPER_LANGUAGES}
                                    accent="emerald"
                                />
                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                    Used for subtitles, AI explanations, and generated notes.
                                </p>
                            </div>
                        </ScopeAwareField>
                    </div>
                </SettingsCard>
            </SettingsSection>
        </>
    );
}

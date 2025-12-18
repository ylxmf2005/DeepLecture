"use client";

import { useState, useEffect } from "react";
import { BrainCircuit, Globe, Sparkles } from "lucide-react";
import { useShallow } from "zustand/react/shallow";
import { CustomSelect } from "@/components/ui/CustomSelect";
import { WHISPER_LANGUAGES } from "@/lib/languages";
import { useGlobalSettingsStore } from "@/stores/useGlobalSettingsStore";
import { SettingsSection, SettingsCard } from "./SettingsSection";
import type { SettingsTabProps } from "./types";

export function GeneralTab(_props: SettingsTabProps) {
    const { language, learnerProfile } = useGlobalSettingsStore(
        useShallow((state) => ({
            language: state.language,
            learnerProfile: state.learnerProfile,
        }))
    );

    const setOriginalLanguage = useGlobalSettingsStore((s) => s.setOriginalLanguage);
    const setTranslatedLanguage = useGlobalSettingsStore((s) => s.setTranslatedLanguage);
    const setLearnerProfile = useGlobalSettingsStore((s) => s.setLearnerProfile);

    const [draftLearnerProfile, setDraftLearnerProfile] = useState(learnerProfile);

    useEffect(() => {
        setDraftLearnerProfile(learnerProfile);
    }, [learnerProfile]);

    return (
        <>
            {/* Learning Preferences Section */}
            <SettingsSection icon={BrainCircuit} title="Learning Preferences" accentColor="blue">
                <SettingsCard>
                    <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                        Customize your AI learning experience. Tell us about your background and goals to get tailored explanations and notes.
                    </p>
                    <div className="relative">
                        <textarea
                            value={draftLearnerProfile}
                            onChange={(e) => setDraftLearnerProfile(e.target.value)}
                            rows={4}
                            placeholder="e.g. I know basic Python, I am preparing for the final exam, please skip trivial chit-chat and focus on problem-solving steps."
                            className="w-full px-4 py-3 rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 text-sm resize-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all placeholder:text-gray-400"
                        />
                        <div className="absolute bottom-3 right-3">
                            {learnerProfile && (
                                <span className="text-[10px] text-gray-400 bg-white dark:bg-gray-800 px-2 py-1 rounded-full border border-gray-100 dark:border-gray-700 shadow-sm">
                                    {learnerProfile.length} chars
                                </span>
                            )}
                        </div>
                    </div>
                    <div className="flex justify-end">
                        <button
                            type="button"
                            onClick={() => setLearnerProfile(draftLearnerProfile.trim())}
                            className="inline-flex items-center px-4 py-2 rounded-lg bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 transition-colors shadow-sm hover:shadow-md active:scale-95"
                        >
                            <Sparkles className="w-3 h-3 mr-2" />
                            Apply Preferences
                        </button>
                    </div>
                </SettingsCard>
            </SettingsSection>

            {/* Language Settings Section */}
            <SettingsSection icon={Globe} title="Language Settings" accentColor="emerald">
                <SettingsCard>
                    <div className="space-y-4">
                        <div className="space-y-2">
                            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                                Source Language
                            </label>
                            <CustomSelect
                                value={language.original}
                                onChange={setOriginalLanguage}
                                options={WHISPER_LANGUAGES}
                                accent="emerald"
                            />
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                The language spoken in the video audio.
                            </p>
                        </div>

                        <div className="space-y-2">
                            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                                Target Language
                            </label>
                            <CustomSelect
                                value={language.translated}
                                onChange={setTranslatedLanguage}
                                options={WHISPER_LANGUAGES}
                                accent="emerald"
                            />
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                Used for subtitles, AI explanations, and generated notes.
                            </p>
                        </div>
                    </div>
                </SettingsCard>
            </SettingsSection>
        </>
    );
}

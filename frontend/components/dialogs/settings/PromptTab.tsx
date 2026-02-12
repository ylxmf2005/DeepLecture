"use client";

import { useEffect, useState } from "react";
import { FileText, Loader2, RotateCcw } from "lucide-react";
import { getAppConfig, PromptFunctionConfig } from "@/lib/api";
import { CustomSelect } from "@/components/ui/CustomSelect";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";
import { SettingsSection, SettingsCard } from "./SettingsSection";
import { ScopeAwareField } from "./ScopeAwareField";
import type { SettingsTabProps } from "./types";

const log = logger.scope("PromptTab");

const PROMPT_LABELS: Record<string, { label: string; desc: string }> = {
    ask_video: { label: "Video Q&A", desc: "Answer questions about video content" },
    ask_summarize_context: { label: "Context Summary", desc: "Summarize video context" },
    note_outline: { label: "Note Outline", desc: "Generate note structure" },
    note_part: { label: "Note Content", desc: "Generate note sections" },
    timeline_segmentation: { label: "Timeline Segmentation", desc: "Divide video into segments" },
    timeline_explanation: { label: "Timeline Explanation", desc: "Explain timeline segments" },
    subtitle_background: { label: "Subtitle Background", desc: "Generate background context" },
    subtitle_enhance_translate: { label: "Subtitle Enhancement", desc: "Enhance and translate subtitles" },
    explanation_system: { label: "Explanation System", desc: "System prompt for explanations" },
    explanation_user: { label: "Explanation User", desc: "User prompt for explanations" },
    slide_lecture: { label: "Slide Lecture", desc: "Generate lecture from slides" },
};

export function PromptTab({ scope, settings }: SettingsTabProps) {
    const isVideoScope = scope === "video";
    const { values, isOverridden, clearField } = settings;
    const { ai } = values;

    const [loading, setLoading] = useState(true);
    const [promptConfigs, setPromptConfigs] = useState<Record<string, PromptFunctionConfig>>({});

    useEffect(() => {
        const fetchConfig = async () => {
            setLoading(true);
            try {
                const config = await getAppConfig();
                setPromptConfigs(config.prompts);
            } catch (error) {
                log.error("Failed to fetch app config", toError(error));
            } finally {
                setLoading(false);
            }
        };
        fetchConfig();
    }, []);

    const getEffectivePrompt = (funcId: string) => {
        return ai.prompts[funcId] || promptConfigs[funcId]?.defaultImplId || "";
    };

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-12 space-y-3">
                <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
                <span className="text-sm text-gray-500 font-medium">Loading prompts...</span>
            </div>
        );
    }

    return (
        <SettingsSection icon={FileText} title="Prompt Templates" accentColor="orange">
            <SettingsCard>
                <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed mb-4">
                    Customize AI behavior by selecting different prompt templates for each function.
                </p>
                <div className="space-y-4">
                    {Object.entries(promptConfigs).map(([funcId, config]) => {
                        const meta = PROMPT_LABELS[funcId] || { label: funcId, desc: "" };
                        const effectiveValue = getEffectivePrompt(funcId);
                        const isCustom = ai.prompts[funcId] && ai.prompts[funcId] !== config.defaultImplId;

                        const options = config.options.map((opt) => ({
                            value: opt.id,
                            label: `${opt.name}${opt.isDefault ? " (Default)" : ""}`,
                        }));

                        return (
                            <ScopeAwareField key={funcId} path="ai.prompts" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
                                                {meta.label}
                                            </span>
                                            {meta.desc && (
                                                <p className="text-[10px] text-gray-400">{meta.desc}</p>
                                            )}
                                        </div>
                                        {isCustom && (
                                            <button
                                                onClick={() => settings.resetAIPrompt(funcId)}
                                                className="text-[10px] text-orange-600 hover:text-orange-700 flex items-center gap-1"
                                            >
                                                <RotateCcw className="w-2.5 h-2.5" />
                                                Reset
                                            </button>
                                        )}
                                    </div>
                                    <CustomSelect
                                        value={effectiveValue}
                                        onChange={(v) => {
                                            if (v === config.defaultImplId) {
                                                settings.resetAIPrompt(funcId);
                                            } else {
                                                settings.setAIPrompt(funcId, v);
                                            }
                                        }}
                                        options={options}
                                        accent="orange"
                                    />
                                </div>
                            </ScopeAwareField>
                        );
                    })}
                </div>
            </SettingsCard>
        </SettingsSection>
    );
}

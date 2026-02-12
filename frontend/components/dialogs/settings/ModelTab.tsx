"use client";

import { useEffect, useState } from "react";
import { Cpu, Volume2, Loader2, RotateCcw } from "lucide-react";
import { getAppConfig, ModelOption } from "@/lib/api";
import { CustomSelect } from "@/components/ui/CustomSelect";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";
import { SettingsSection, SettingsCard } from "./SettingsSection";
import { ScopeAwareField } from "./ScopeAwareField";
import type { SettingsTabProps } from "./types";

const log = logger.scope("ModelTab");

export function ModelTab({ scope, settings }: SettingsTabProps) {
    const isVideoScope = scope === "video";
    const { values, isOverridden, clearField } = settings;
    const { ai } = values;

    const [llmModels, setLlmModels] = useState<ModelOption[]>([]);
    const [defaultLlmModel, setDefaultLlmModel] = useState<string>("");
    const [ttsModels, setTtsModels] = useState<ModelOption[]>([]);
    const [defaultTtsModel, setDefaultTtsModel] = useState<string>("");
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchConfig = async () => {
            setLoading(true);
            try {
                const config = await getAppConfig();
                setLlmModels(config.llm.models);
                setDefaultLlmModel(config.llm.defaultModel);
                setTtsModels(config.tts.models);
                setDefaultTtsModel(config.tts.defaultModel);
            } catch (error) {
                log.error("Failed to fetch app config", toError(error));
            } finally {
                setLoading(false);
            }
        };
        fetchConfig();
    }, []);

    const getEffectiveLlmModel = () => ai.llmModel || defaultLlmModel;
    const getEffectiveTtsModel = () => ai.ttsModel || defaultTtsModel;

    const llmOptions = llmModels.map((m) => ({
        value: m.id,
        label: `${m.name} (${m.provider})${m.id === defaultLlmModel ? " - Default" : ""}`,
    }));

    const ttsOptions = ttsModels.map((m) => ({
        value: m.id,
        label: `${m.name} (${m.provider})${m.id === defaultTtsModel ? " - Default" : ""}`,
    }));

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-12 space-y-3">
                <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
                <span className="text-sm text-gray-500 font-medium">Loading models...</span>
            </div>
        );
    }

    return (
        <>
            {/* LLM Model Selection */}
            <SettingsSection icon={Cpu} title="LLM Model" accentColor="indigo">
                <SettingsCard>
                    <ScopeAwareField path="ai.llmModel" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <label className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                                    Model for AI Tasks
                                </label>
                                {ai.llmModel && !isVideoScope && (
                                    <button
                                        onClick={() => settings.setAILlmModel(null)}
                                        className="text-xs text-indigo-600 hover:text-indigo-700 flex items-center gap-1"
                                    >
                                        <RotateCcw className="w-3 h-3" />
                                        Reset
                                    </button>
                                )}
                            </div>
                            <CustomSelect
                                value={getEffectiveLlmModel()}
                                onChange={(v) => settings.setAILlmModel(v === defaultLlmModel ? null : v)}
                                options={llmOptions}
                                accent="indigo"
                            />
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                Used for Q&A, explanations, notes, and timeline generation.
                            </p>
                        </div>
                    </ScopeAwareField>
                </SettingsCard>
            </SettingsSection>

            {/* TTS Model Selection */}
            <SettingsSection icon={Volume2} title="TTS Model" accentColor="rose">
                <SettingsCard>
                    <ScopeAwareField path="ai.ttsModel" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <label className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                                    Voice for Audio
                                </label>
                                {ai.ttsModel && !isVideoScope && (
                                    <button
                                        onClick={() => settings.setAITtsModel(null)}
                                        className="text-xs text-rose-600 hover:text-rose-700 flex items-center gap-1"
                                    >
                                        <RotateCcw className="w-3 h-3" />
                                        Reset
                                    </button>
                                )}
                            </div>
                            <CustomSelect
                                value={getEffectiveTtsModel()}
                                onChange={(v) => settings.setAITtsModel(v === defaultTtsModel ? null : v)}
                                options={ttsOptions}
                                accent="rose"
                            />
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                Used for voiceover and slide lecture audio.
                            </p>
                        </div>
                    </ScopeAwareField>
                </SettingsCard>
            </SettingsSection>
        </>
    );
}

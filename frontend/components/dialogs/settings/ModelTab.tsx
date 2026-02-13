"use client";

import { useEffect, useMemo, useState } from "react";
import { Cpu, Volume2, Loader2, RotateCcw } from "lucide-react";
import { getAppConfig, ModelOption } from "@/lib/api";
import { CustomSelect } from "@/components/ui/CustomSelect";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";
import { SettingsSection, SettingsCard } from "./SettingsSection";
import { ScopeAwareField } from "./ScopeAwareField";
import type { SettingsTabProps } from "./types";

const log = logger.scope("ModelTab");
const FOLLOW_DEFAULT_VALUE = "__FOLLOW_DEFAULT__";

const TASK_MODEL_META: Record<string, { label: string; llmHint?: string; ttsHint?: string }> = {
    subtitle_translation: {
        label: "Subtitle Translation",
        llmHint: "Used for subtitle enhancement and translation generation.",
    },
    timeline_generation: {
        label: "Timeline Generation",
        llmHint: "Used when generating lecture timeline summaries.",
    },
    video_generation: {
        label: "Slide Video Generation",
        llmHint: "Used for slide script and narration text generation.",
        ttsHint: "Used for TTS audio synthesis in generated slide videos.",
    },
    voiceover_generation: {
        label: "Voiceover Generation",
        ttsHint: "Used when generating translated voiceover audio tracks.",
    },
    note_generation: {
        label: "Note Generation",
        llmHint: "Used when generating study notes.",
    },
    quiz_generation: {
        label: "Quiz Generation",
        llmHint: "Used when generating quiz questions and explanations.",
    },
    cheatsheet_generation: {
        label: "Cheatsheet Generation",
        llmHint: "Used when generating exam cheatsheets.",
    },
    slide_explanation: {
        label: "Slide Explanation",
        llmHint: "Used when explaining captured slide screenshots.",
    },
    ask_video: {
        label: "Video Q&A",
        llmHint: "Used when answering questions about the video.",
    },
};

function buildModelOptions(models: ModelOption[], defaultModel: string) {
    return models.map((m) => ({
        value: m.id,
        label: `${m.name} (${m.provider})${m.id === defaultModel ? " - Default" : ""}`,
    }));
}

function toNullableModel(value: string, defaultModel: string): string | null {
    return value === defaultModel ? null : value;
}

function humanizeTaskKey(taskKey: string): string {
    return taskKey
        .split("_")
        .filter(Boolean)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
}

export function ModelTab({ scope, settings }: SettingsTabProps) {
    const isVideoScope = scope === "video";
    const { values, isOverridden, clearField } = settings;
    const { ai } = values;

    const [llmModels, setLlmModels] = useState<ModelOption[]>([]);
    const [defaultLlmModel, setDefaultLlmModel] = useState<string>("");
    const [ttsModels, setTtsModels] = useState<ModelOption[]>([]);
    const [defaultTtsModel, setDefaultTtsModel] = useState<string>("");
    const [taskKeys, setTaskKeys] = useState<string[]>([]);
    const [llmTaskKeys, setLlmTaskKeys] = useState<string[]>([]);
    const [ttsTaskKeys, setTtsTaskKeys] = useState<string[]>([]);
    const [llmTaskDefaults, setLlmTaskDefaults] = useState<Record<string, string>>({});
    const [ttsTaskDefaults, setTtsTaskDefaults] = useState<Record<string, string>>({});
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
                setTaskKeys(config.taskKeys ?? []);
                setLlmTaskKeys(config.llmTaskKeys ?? []);
                setTtsTaskKeys(config.ttsTaskKeys ?? []);
                setLlmTaskDefaults(config.llm.taskModelDefaults ?? {});
                setTtsTaskDefaults(config.tts.taskModelDefaults ?? {});
            } catch (error) {
                log.error("Failed to fetch app config", toError(error));
            } finally {
                setLoading(false);
            }
        };
        fetchConfig();
    }, []);

    const llmOptions = useMemo(() => buildModelOptions(llmModels, defaultLlmModel), [llmModels, defaultLlmModel]);
    const ttsOptions = useMemo(() => buildModelOptions(ttsModels, defaultTtsModel), [ttsModels, defaultTtsModel]);

    const effectiveGlobalLlm = ai.llmModel || llmTaskDefaults.default || defaultLlmModel;
    const effectiveGlobalTts = ai.ttsModel || ttsTaskDefaults.default || defaultTtsModel;
    const effectiveLlmTaskKeys = llmTaskKeys.length > 0 ? llmTaskKeys : taskKeys;
    const effectiveTtsTaskKeys = ttsTaskKeys.length > 0 ? ttsTaskKeys : taskKeys;

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
            <SettingsSection icon={Cpu} title="LLM Models" accentColor="indigo">
                <SettingsCard>
                    <ScopeAwareField path="ai.llmModel" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <label className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                                    Default LLM Model
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
                                value={effectiveGlobalLlm}
                                onChange={(v) => settings.setAILlmModel(toNullableModel(v, defaultLlmModel))}
                                options={llmOptions}
                                accent="indigo"
                            />
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                Used by tasks set to follow default.
                            </p>
                        </div>
                    </ScopeAwareField>
                </SettingsCard>

                {effectiveLlmTaskKeys.map((taskKey) => {
                    const taskPath = `ai.llmTaskModels.${taskKey}`;
                    const resolvedValue = ai.llmTaskModels?.[taskKey] ?? null;
                    const hasTaskOverride = isVideoScope ? isOverridden(taskPath) : resolvedValue !== null;
                    const rawValue = hasTaskOverride ? resolvedValue : null;
                    const taskMeta = TASK_MODEL_META[taskKey];
                    const llmTaskOptions = [
                        { value: FOLLOW_DEFAULT_VALUE, label: "Follow default model" },
                        ...llmOptions,
                    ];

                    return (
                        <SettingsCard key={`llm-${taskKey}`}>
                            <ScopeAwareField path={taskPath} isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <label className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                                            {taskMeta?.label ?? humanizeTaskKey(taskKey)}
                                        </label>
                                        {hasTaskOverride && !isVideoScope && (
                                            <button
                                                onClick={() => settings.setAILlmTaskModel(taskKey, null)}
                                                className="text-xs text-indigo-600 hover:text-indigo-700 flex items-center gap-1"
                                            >
                                                <RotateCcw className="w-3 h-3" />
                                                Reset
                                            </button>
                                        )}
                                    </div>
                                    <CustomSelect
                                        value={rawValue ?? FOLLOW_DEFAULT_VALUE}
                                        onChange={(v) => settings.setAILlmTaskModel(taskKey, v === FOLLOW_DEFAULT_VALUE ? null : v)}
                                        options={llmTaskOptions}
                                        accent="indigo"
                                    />
                                    <p className="text-xs text-gray-500 dark:text-gray-400">
                                        {hasTaskOverride
                                            ? "Task-level LLM override is active."
                                            : "Following default model."}
                                    </p>
                                </div>
                            </ScopeAwareField>
                        </SettingsCard>
                    );
                })}
            </SettingsSection>

            <SettingsSection icon={Volume2} title="TTS Models" accentColor="rose">
                <SettingsCard>
                    <ScopeAwareField path="ai.ttsModel" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <label className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                                    Default TTS Model
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
                                value={effectiveGlobalTts}
                                onChange={(v) => settings.setAITtsModel(toNullableModel(v, defaultTtsModel))}
                                options={ttsOptions}
                                accent="rose"
                            />
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                Used by tasks set to follow default.
                            </p>
                        </div>
                    </ScopeAwareField>
                </SettingsCard>

                {effectiveTtsTaskKeys.map((taskKey) => {
                    const taskPath = `ai.ttsTaskModels.${taskKey}`;
                    const resolvedValue = ai.ttsTaskModels?.[taskKey] ?? null;
                    const hasTaskOverride = isVideoScope ? isOverridden(taskPath) : resolvedValue !== null;
                    const rawValue = hasTaskOverride ? resolvedValue : null;
                    const taskMeta = TASK_MODEL_META[taskKey];
                    const ttsTaskOptions = [
                        { value: FOLLOW_DEFAULT_VALUE, label: "Follow default model" },
                        ...ttsOptions,
                    ];

                    return (
                        <SettingsCard key={`tts-${taskKey}`}>
                            <ScopeAwareField path={taskPath} isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <label className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                                            {taskMeta?.label ?? humanizeTaskKey(taskKey)}
                                        </label>
                                        {hasTaskOverride && !isVideoScope && (
                                            <button
                                                onClick={() => settings.setAITtsTaskModel(taskKey, null)}
                                                className="text-xs text-rose-600 hover:text-rose-700 flex items-center gap-1"
                                            >
                                                <RotateCcw className="w-3 h-3" />
                                                Reset
                                            </button>
                                        )}
                                    </div>
                                    <CustomSelect
                                        value={rawValue ?? FOLLOW_DEFAULT_VALUE}
                                        onChange={(v) => settings.setAITtsTaskModel(taskKey, v === FOLLOW_DEFAULT_VALUE ? null : v)}
                                        options={ttsTaskOptions}
                                        accent="rose"
                                    />
                                    <p className="text-xs text-gray-500 dark:text-gray-400">
                                        {hasTaskOverride
                                            ? "Task-level TTS override is active."
                                            : "Following default model."}
                                    </p>
                                </div>
                            </ScopeAwareField>
                        </SettingsCard>
                    );
                })}
            </SettingsSection>
        </>
    );
}

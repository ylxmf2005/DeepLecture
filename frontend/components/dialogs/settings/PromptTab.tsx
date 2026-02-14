"use client";

import { useEffect, useState } from "react";
import { FileText, Loader2, Plus, RotateCcw } from "lucide-react";
import { createPromptTemplate, getAppConfig, PromptFunctionConfig } from "@/lib/api";
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
    const [showCreate, setShowCreate] = useState(false);
    const [creating, setCreating] = useState(false);
    const [createError, setCreateError] = useState<string | null>(null);
    const [createForm, setCreateForm] = useState({
        funcId: "",
        implId: "",
        name: "",
        description: "",
        systemTemplate: "",
        userTemplate: "",
    });

    const fetchConfig = async () => {
        setLoading(true);
        try {
            const config = await getAppConfig();
            setPromptConfigs(config.prompts);
            const firstFuncId = Object.keys(config.prompts)[0] || "";
            setCreateForm((prev) => ({
                ...prev,
                funcId: prev.funcId || firstFuncId,
            }));
        } catch (error) {
            log.error("Failed to fetch app config", toError(error));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchConfig().catch((error) => {
            log.error("Failed to initialize prompt config", toError(error));
        });
        // eslint-disable-next-line react-hooks/exhaustive-deps
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
                <div className="flex items-start justify-between gap-3 mb-4">
                    <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                        Customize AI behavior by selecting different prompt templates for each function.
                    </p>
                    {!isVideoScope && (
                        <button
                            type="button"
                            onClick={() => {
                                setShowCreate((v) => !v);
                                setCreateError(null);
                            }}
                            className="inline-flex items-center gap-1.5 rounded-md border border-orange-200 px-2.5 py-1 text-xs font-medium text-orange-700 hover:bg-orange-50"
                        >
                            <Plus className="w-3.5 h-3.5" />
                            New Template
                        </button>
                    )}
                </div>
                {showCreate && !isVideoScope && (
                    <div className="mb-4 rounded-lg border border-orange-200 bg-orange-50/50 p-3 space-y-2">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                            <select
                                value={createForm.funcId}
                                onChange={(e) => setCreateForm((prev) => ({ ...prev, funcId: e.target.value }))}
                                className="rounded-md border border-gray-200 px-2 py-1.5 text-xs"
                            >
                                {Object.keys(promptConfigs).map((funcId) => (
                                    <option key={funcId} value={funcId}>{funcId}</option>
                                ))}
                            </select>
                            <input
                                value={createForm.implId}
                                onChange={(e) => setCreateForm((prev) => ({ ...prev, implId: e.target.value }))}
                                placeholder="impl_id (e.g. concise_v1)"
                                className="rounded-md border border-gray-200 px-2 py-1.5 text-xs"
                            />
                            <input
                                value={createForm.name}
                                onChange={(e) => setCreateForm((prev) => ({ ...prev, name: e.target.value }))}
                                placeholder="Display name"
                                className="rounded-md border border-gray-200 px-2 py-1.5 text-xs"
                            />
                        </div>
                        <input
                            value={createForm.description}
                            onChange={(e) => setCreateForm((prev) => ({ ...prev, description: e.target.value }))}
                            placeholder="Description (optional)"
                            className="w-full rounded-md border border-gray-200 px-2 py-1.5 text-xs"
                        />
                        <textarea
                            rows={3}
                            value={createForm.systemTemplate}
                            onChange={(e) => setCreateForm((prev) => ({ ...prev, systemTemplate: e.target.value }))}
                            placeholder="System template (optional). Placeholders use {name}."
                            className="w-full rounded-md border border-gray-200 px-2 py-1.5 text-xs"
                        />
                        <textarea
                            rows={3}
                            value={createForm.userTemplate}
                            onChange={(e) => setCreateForm((prev) => ({ ...prev, userTemplate: e.target.value }))}
                            placeholder="User template (optional). Placeholders use {name}."
                            className="w-full rounded-md border border-gray-200 px-2 py-1.5 text-xs"
                        />
                        {createError && (
                            <p className="text-xs text-red-600">{createError}</p>
                        )}
                        <div className="flex justify-end gap-2">
                            <button
                                type="button"
                                onClick={() => {
                                    setShowCreate(false);
                                    setCreateError(null);
                                }}
                                className="rounded-md border border-gray-200 px-3 py-1.5 text-xs"
                            >
                                Cancel
                            </button>
                            <button
                                type="button"
                                disabled={creating}
                                onClick={async () => {
                                    try {
                                        setCreating(true);
                                        setCreateError(null);
                                        const created = await createPromptTemplate({
                                            funcId: createForm.funcId.trim(),
                                            implId: createForm.implId.trim(),
                                            name: createForm.name.trim(),
                                            description: createForm.description.trim() || undefined,
                                            systemTemplate: createForm.systemTemplate,
                                            userTemplate: createForm.userTemplate,
                                        });
                                        await fetchConfig();
                                        settings.setAIPrompt(created.funcId, created.implId);
                                        setShowCreate(false);
                                        setCreateForm((prev) => ({
                                            ...prev,
                                            implId: "",
                                            name: "",
                                            description: "",
                                            systemTemplate: "",
                                            userTemplate: "",
                                        }));
                                    } catch (error) {
                                        setCreateError(toError(error).message);
                                    } finally {
                                        setCreating(false);
                                    }
                                }}
                                className="rounded-md bg-orange-600 px-3 py-1.5 text-xs text-white disabled:opacity-60"
                            >
                                {creating ? "Creating..." : "Create"}
                            </button>
                        </div>
                    </div>
                )}
                <div className="space-y-4">
                    {Object.entries(promptConfigs).map(([funcId, config]) => {
                        const meta = PROMPT_LABELS[funcId] || { label: funcId, desc: "" };
                        const effectiveValue = getEffectivePrompt(funcId);
                        const isCustom = ai.prompts[funcId] && ai.prompts[funcId] !== config.defaultImplId;

                        const options = config.options.map((opt) => ({
                            value: opt.id,
                            label:
                                config.options.length === 1 && opt.isDefault && opt.name.toLowerCase() === "default"
                                    ? "Default"
                                    : `${opt.name}${opt.isDefault ? " (Default)" : ""}`,
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

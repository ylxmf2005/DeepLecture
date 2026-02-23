"use client";

import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { FileText, Loader2, Plus, RotateCcw } from "lucide-react";
import { createPromptTemplate, getAppConfig, PromptFunctionConfig } from "@/lib/api";
import { CustomSelect } from "@/components/ui/CustomSelect";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";
import { cn } from "@/lib/utils";
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
    cheatsheet_extraction: { label: "Cheatsheet Extraction", desc: "Extract key knowledge for cheatsheets" },
    cheatsheet_rendering: { label: "Cheatsheet Rendering", desc: "Render cheatsheet layout" },
    quiz_generation: { label: "Quiz Generation", desc: "Generate quiz questions" },
};

const FUNC_PLACEHOLDERS: Record<string, { allowed: string[]; required: string[] }> = {
    timeline_segmentation: {
        allowed: ["segments", "language", "learner_profile"],
        required: ["segments"],
    },
    timeline_explanation: {
        allowed: ["segments", "language", "chunk_start", "chunk_end", "learner_profile"],
        required: ["segments", "chunk_start", "chunk_end"],
    },
    slide_lecture: {
        allowed: ["deck_id", "page_index", "total_pages", "source_language", "target_language", "neighbor_images", "previous_transcript", "accumulated_summaries"],
        required: ["deck_id", "page_index", "total_pages"],
    },
    ask_video: {
        allowed: ["learner_profile", "language", "context_block", "history_block", "question"],
        required: ["question"],
    },
    ask_summarize_context: {
        allowed: ["learner_profile", "language", "context_block"],
        required: ["context_block"],
    },
    subtitle_background: {
        allowed: ["transcript_text"],
        required: ["transcript_text"],
    },
    subtitle_enhance_translate: {
        allowed: ["background", "segments", "target_language"],
        required: ["segments"],
    },
    explanation_system: {
        allowed: ["learner_profile", "output_language"],
        required: [],
    },
    explanation_user: {
        allowed: ["timestamp", "subtitle_context"],
        required: ["timestamp"],
    },
    note_outline: {
        allowed: ["language", "context_block", "instruction", "profile", "max_parts"],
        required: ["language", "context_block"],
    },
    note_part: {
        allowed: ["language", "context_block", "instruction", "profile", "part", "outline"],
        required: ["language", "context_block", "part"],
    },
    cheatsheet_extraction: {
        allowed: ["context", "language", "subject_type", "user_instruction"],
        required: ["context", "language"],
    },
    cheatsheet_rendering: {
        allowed: ["knowledge_items_json", "language", "target_pages", "min_criticality"],
        required: ["knowledge_items_json", "language"],
    },
    quiz_generation: {
        allowed: ["knowledge_items_json", "language", "question_count", "user_instruction"],
        required: ["knowledge_items_json", "language"],
    },
};

function slugify(name: string): string {
    return name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_|_$/g, "");
}

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
    const [implIdManuallyEdited, setImplIdManuallyEdited] = useState(false);

    const funcIdOptions = useMemo(
        () =>
            Object.keys(promptConfigs).map((funcId) => ({
                value: funcId,
                label: PROMPT_LABELS[funcId]?.label || funcId,
            })),
        [promptConfigs],
    );

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

    const handleCreate = async () => {
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
            setImplIdManuallyEdited(false);
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
    };

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
                            className="inline-flex items-center gap-1.5 rounded-md border border-orange-200 dark:border-orange-800 px-2.5 py-1 text-xs font-medium text-orange-700 dark:text-orange-400 hover:bg-orange-50 dark:hover:bg-orange-900/30"
                        >
                            <Plus className="w-3.5 h-3.5" />
                            New Template
                        </button>
                    )}
                </div>
                <AnimatePresence initial={false}>
                    {showCreate && !isVideoScope && (
                        <motion.div
                            key="create-form"
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2, ease: "easeInOut" }}
                            className="overflow-hidden"
                        >
                            <div className="mb-4 rounded-lg border border-orange-200 dark:border-orange-800 bg-white dark:bg-gray-800/50 p-4 space-y-0">
                                {/* Section 1 — Function Selection */}
                                <div className="space-y-1.5">
                                    <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
                                        Prompt Function
                                    </label>
                                    <CustomSelect
                                        value={createForm.funcId}
                                        onChange={(v) => setCreateForm((prev) => ({ ...prev, funcId: v }))}
                                        options={funcIdOptions}
                                        accent="orange"
                                    />
                                    {createForm.funcId && PROMPT_LABELS[createForm.funcId] && (
                                        <p className="text-[11px] text-gray-500 dark:text-gray-400">
                                            {PROMPT_LABELS[createForm.funcId].desc}
                                        </p>
                                    )}
                                </div>

                                {/* Section 2 — Identity */}
                                <div className="border-t border-gray-100 dark:border-gray-700 pt-3 mt-3 space-y-2.5">
                                    <div className="space-y-1">
                                        <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
                                            Template Name
                                        </label>
                                        <input
                                            value={createForm.name}
                                            onChange={(e) => {
                                                const name = e.target.value;
                                                setCreateForm((prev) => ({
                                                    ...prev,
                                                    name,
                                                    implId: implIdManuallyEdited ? prev.implId : slugify(name),
                                                }));
                                            }}
                                            placeholder="e.g. Concise Summary v2"
                                            className="w-full rounded-md border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 px-2.5 py-1.5 text-xs text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500"
                                        />
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                                        <div className="space-y-1">
                                            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
                                                Template ID
                                            </label>
                                            <input
                                                value={createForm.implId}
                                                onChange={(e) => {
                                                    setImplIdManuallyEdited(true);
                                                    setCreateForm((prev) => ({ ...prev, implId: e.target.value }));
                                                }}
                                                placeholder="auto_generated_from_name"
                                                className="w-full rounded-md border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 px-2.5 py-1.5 text-xs font-mono text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500"
                                            />
                                            <p className="text-[10px] text-gray-400 dark:text-gray-500">
                                                Auto-generated from name
                                            </p>
                                        </div>
                                        <div className="space-y-1">
                                            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
                                                Description <span className="font-normal text-gray-400">(optional)</span>
                                            </label>
                                            <input
                                                value={createForm.description}
                                                onChange={(e) => setCreateForm((prev) => ({ ...prev, description: e.target.value }))}
                                                placeholder="Brief description of this template"
                                                className="w-full rounded-md border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 px-2.5 py-1.5 text-xs text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500"
                                            />
                                        </div>
                                    </div>
                                </div>

                                {/* Section 3 — Templates */}
                                <div className="border-t border-gray-100 dark:border-gray-700 pt-3 mt-3 space-y-2.5">
                                    <div className="space-y-1">
                                        <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
                                            System Template
                                        </label>
                                        <textarea
                                            rows={4}
                                            value={createForm.systemTemplate}
                                            onChange={(e) => setCreateForm((prev) => ({ ...prev, systemTemplate: e.target.value }))}
                                            placeholder="System instructions for the AI. Use {placeholder} for variables."
                                            className="w-full rounded-md border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 px-2.5 py-1.5 text-xs font-mono text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 resize-y min-h-[80px] focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500"
                                        />
                                    </div>
                                    <div className="space-y-1">
                                        <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
                                            User Template
                                        </label>
                                        <textarea
                                            rows={4}
                                            value={createForm.userTemplate}
                                            onChange={(e) => setCreateForm((prev) => ({ ...prev, userTemplate: e.target.value }))}
                                            placeholder="User message template. Use {placeholder} for variables."
                                            className="w-full rounded-md border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 px-2.5 py-1.5 text-xs font-mono text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 resize-y min-h-[80px] focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500"
                                        />
                                    </div>

                                    {/* Available Placeholders */}
                                    {createForm.funcId && FUNC_PLACEHOLDERS[createForm.funcId] && (
                                        <div className="space-y-1.5">
                                            <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400">
                                                Available Placeholders
                                            </span>
                                            <div className="flex flex-wrap gap-1.5">
                                                {FUNC_PLACEHOLDERS[createForm.funcId].allowed.map((v) => {
                                                    const isRequired = FUNC_PLACEHOLDERS[createForm.funcId].required.includes(v);
                                                    return (
                                                        <button
                                                            key={v}
                                                            type="button"
                                                            onClick={() => navigator.clipboard.writeText(`{${v}}`)}
                                                            title={`Click to copy {${v}}`}
                                                            className={cn(
                                                                "inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-[11px] font-mono cursor-pointer transition-colors",
                                                                isRequired
                                                                    ? "bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300 hover:bg-orange-200 dark:hover:bg-orange-900/50"
                                                                    : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600",
                                                            )}
                                                        >
                                                            {`{${v}}`}{isRequired && <span className="text-orange-500">*</span>}
                                                        </button>
                                                    );
                                                })}
                                            </div>
                                            <p className="text-[10px] text-gray-400 dark:text-gray-500">
                                                <span className="text-orange-500">*</span> = required · click to copy
                                            </p>
                                        </div>
                                    )}
                                </div>

                                {/* Error display */}
                                {createError && (
                                    <div className="mt-3 rounded-md border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-3 py-2">
                                        <p className="text-xs text-red-700 dark:text-red-400">{createError}</p>
                                    </div>
                                )}

                                {/* Buttons */}
                                <div className="flex justify-end gap-2 pt-3 mt-3 border-t border-gray-100 dark:border-gray-700">
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setShowCreate(false);
                                            setCreateError(null);
                                        }}
                                        className="rounded-md border border-gray-200 dark:border-gray-600 px-3 py-1.5 text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        type="button"
                                        disabled={creating}
                                        onClick={handleCreate}
                                        className="inline-flex items-center gap-1.5 rounded-md bg-orange-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-orange-700 disabled:opacity-60 transition-colors"
                                    >
                                        {creating && <Loader2 className="w-3 h-3 animate-spin" />}
                                        {creating ? "Creating…" : "Create Template"}
                                    </button>
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
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

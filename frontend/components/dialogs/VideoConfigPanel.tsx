"use client";

import { useEffect, useState, useRef } from "react";
import {
    X,
    Globe,
    Cpu,
    Volume2,
    FileText,
    RotateCcw,
    Loader2,
    SlidersHorizontal,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getAppConfig, type ModelOption } from "@/lib/api";
import { WHISPER_LANGUAGES } from "@/lib/languages";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";
import { useFocusTrap } from "@/hooks/useFocusTrap";
import { useConfirmDialog } from "@/contexts/ConfirmDialogContext";
import { CustomSelect } from "@/components/ui/CustomSelect";
import { SettingsSection, SettingsCard } from "./settings/SettingsSection";
import type { PerVideoConfig, NoteContextMode } from "@/stores/types";

const log = logger.scope("VideoConfigPanel");

interface VideoConfigPanelProps {
    isOpen: boolean;
    onClose: () => void;
    videoName: string;
    overrides: PerVideoConfig;
    isOverridden: (field: string) => boolean;
    setOverrides: (updates: PerVideoConfig) => void;
    clearOverride: (field: string) => void;
    clearAllOverrides: () => Promise<void>;
}

export function VideoConfigPanel({
    isOpen,
    onClose,
    videoName,
    overrides,
    isOverridden,
    setOverrides,
    clearOverride,
    clearAllOverrides,
}: VideoConfigPanelProps) {
    const dialogRef = useRef<HTMLDivElement>(null);
    const dialogA11yProps = useFocusTrap({ isOpen, onClose, containerRef: dialogRef });
    const { confirm } = useConfirmDialog();

    // Model options (fetched once on open)
    const [llmModels, setLlmModels] = useState<ModelOption[]>([]);
    const [defaultLlmModel, setDefaultLlmModel] = useState("");
    const [ttsModels, setTtsModels] = useState<ModelOption[]>([]);
    const [defaultTtsModel, setDefaultTtsModel] = useState("");
    const [modelsLoading, setModelsLoading] = useState(true);

    useEffect(() => {
        if (!isOpen) return;

        const fetchModels = async () => {
            setModelsLoading(true);
            try {
                const config = await getAppConfig();
                setLlmModels(config.llm.models);
                setDefaultLlmModel(config.llm.defaultModel);
                setTtsModels(config.tts.models);
                setDefaultTtsModel(config.tts.defaultModel);
            } catch (error) {
                log.error("Failed to fetch app config", toError(error));
            } finally {
                setModelsLoading(false);
            }
        };

        fetchModels();
    }, [isOpen]);

    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = "hidden";
        }
        return () => {
            document.body.style.overflow = "unset";
        };
    }, [isOpen]);

    if (!isOpen) return null;

    const handleResetAll = async () => {
        const confirmed = await confirm({
            title: "Reset Video Configuration",
            message: "Remove all per-video overrides? This video will use your global settings.",
            confirmLabel: "Reset All",
            variant: "danger",
        });
        if (confirmed) {
            await clearAllOverrides();
        }
    };

    const hasAnyOverrides = Object.keys(overrides).length > 0;

    const llmOptions = llmModels.map((m) => ({
        value: m.id,
        label: `${m.name} (${m.provider})${m.id === defaultLlmModel ? " - Default" : ""}`,
    }));

    const ttsOptions = ttsModels.map((m) => ({
        value: m.id,
        label: `${m.name} (${m.provider})${m.id === defaultTtsModel ? " - Default" : ""}`,
    }));

    const noteContextOptions = [
        { value: "subtitle", label: "Subtitle Only" },
        { value: "slide", label: "Slide Only" },
        { value: "both", label: "Both" },
    ];

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
            <div
                ref={dialogRef}
                {...dialogA11yProps}
                aria-labelledby="video-config-title"
                className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col animate-in zoom-in-95 duration-200"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-800">
                    <div>
                        <h2 id="video-config-title" className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                            Video Configuration
                        </h2>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 truncate max-w-md">
                            {videoName}
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        {hasAnyOverrides && (
                            <button
                                onClick={handleResetAll}
                                className="text-xs text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 flex items-center gap-1 px-2 py-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                            >
                                <RotateCcw className="w-3 h-3" />
                                Reset All
                            </button>
                        )}
                        <button
                            onClick={onClose}
                            aria-label="Close video configuration"
                            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 transition-colors"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6 bg-gray-50/50 dark:bg-gray-900/50">
                    <div className="max-w-xl mx-auto space-y-8">
                        <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                            Override global settings for this video. Fields without overrides inherit from your global preferences.
                        </p>

                        {/* Language */}
                        <SettingsSection icon={Globe} title="Language" accentColor="emerald">
                            <SettingsCard>
                                <div className="space-y-4">
                                    <OverridableSelect
                                        label="Source Language"
                                        description="Language spoken in the video"
                                        value={overrides.language?.original ?? ""}
                                        onChange={(v) => setOverrides({ language: { original: v } })}
                                        options={WHISPER_LANGUAGES}
                                        isOverridden={isOverridden("language.original")}
                                        onReset={() => clearOverride("language.original")}
                                        accent="emerald"
                                    />
                                    <OverridableSelect
                                        label="Target Language"
                                        description="Used for translations, explanations, notes"
                                        value={overrides.language?.translated ?? ""}
                                        onChange={(v) => setOverrides({ language: { translated: v } })}
                                        options={WHISPER_LANGUAGES}
                                        isOverridden={isOverridden("language.translated")}
                                        onReset={() => clearOverride("language.translated")}
                                        accent="emerald"
                                    />
                                </div>
                            </SettingsCard>
                        </SettingsSection>

                        {/* AI Models */}
                        {modelsLoading ? (
                            <div className="flex flex-col items-center py-8 space-y-2">
                                <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
                                <span className="text-xs text-gray-500">Loading models...</span>
                            </div>
                        ) : (
                            <SettingsSection icon={Cpu} title="AI Models" accentColor="indigo">
                                <SettingsCard>
                                    <div className="space-y-4">
                                        <OverridableSelect
                                            label="LLM Model"
                                            description="Used for Q&A, explanations, notes, timeline"
                                            value={overrides.ai?.llmModel ?? ""}
                                            onChange={(v) => setOverrides({ ai: { llmModel: v || null } })}
                                            options={llmOptions}
                                            isOverridden={isOverridden("ai.llmModel")}
                                            onReset={() => clearOverride("ai.llmModel")}
                                            accent="indigo"
                                        />
                                        <OverridableSelect
                                            label="TTS Model"
                                            description="Used for voiceover audio"
                                            value={overrides.ai?.ttsModel ?? ""}
                                            onChange={(v) => setOverrides({ ai: { ttsModel: v || null } })}
                                            options={ttsOptions}
                                            isOverridden={isOverridden("ai.ttsModel")}
                                            onReset={() => clearOverride("ai.ttsModel")}
                                            accent="rose"
                                        />
                                    </div>
                                </SettingsCard>
                            </SettingsSection>
                        )}

                        {/* Content Settings */}
                        <SettingsSection icon={FileText} title="Content" accentColor="violet">
                            <SettingsCard>
                                <div className="space-y-4">
                                    <OverridableSelect
                                        label="Note Context"
                                        description="Source material for note generation"
                                        value={overrides.note?.contextMode ?? ""}
                                        onChange={(v) => setOverrides({ note: { contextMode: v as NoteContextMode } })}
                                        options={noteContextOptions}
                                        isOverridden={isOverridden("note.contextMode")}
                                        onReset={() => clearOverride("note.contextMode")}
                                        accent="violet"
                                    />
                                    <OverridableTextarea
                                        label="Learner Profile"
                                        description="Background and goals for AI personalization"
                                        value={overrides.learnerProfile ?? ""}
                                        onChange={(v) => setOverrides({ learnerProfile: v })}
                                        isOverridden={isOverridden("learnerProfile")}
                                        onReset={() => clearOverride("learnerProfile")}
                                        placeholder="e.g. I'm a beginner in linear algebra, focus on intuition over proofs."
                                    />
                                </div>
                            </SettingsCard>
                        </SettingsSection>
                    </div>
                </div>
            </div>
        </div>
    );
}

// ─── Reusable Sub-Components ────────────────────────────────────────────────

function ResetButton({ onClick }: { onClick: () => void }) {
    return (
        <button
            onClick={onClick}
            className="text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 flex items-center gap-1"
            title="Reset to global default"
        >
            <RotateCcw className="w-3 h-3" />
            Reset
        </button>
    );
}

function OverridableSelect({
    label,
    description,
    value,
    onChange,
    options,
    isOverridden,
    onReset,
    accent = "indigo",
}: {
    label: string;
    description: string;
    value: string;
    onChange: (value: string) => void;
    options: Array<{ value: string; label: string }>;
    isOverridden: boolean;
    onReset: () => void;
    accent?: "indigo" | "emerald" | "rose" | "cyan" | "violet" | "orange";
}) {
    return (
        <div className="space-y-1.5">
            <div className="flex items-center justify-between">
                <div>
                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                        {label}
                    </label>
                    {isOverridden && (
                        <span className="ml-2 text-[10px] font-medium text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 px-1.5 py-0.5 rounded">
                            Override
                        </span>
                    )}
                </div>
                {isOverridden && <ResetButton onClick={onReset} />}
            </div>
            <CustomSelect
                value={value}
                onChange={onChange}
                options={options}
                accent={accent}
                placeholder="Use global default"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
        </div>
    );
}

function OverridableTextarea({
    label,
    description,
    value,
    onChange,
    isOverridden,
    onReset,
    placeholder,
}: {
    label: string;
    description: string;
    value: string;
    onChange: (value: string) => void;
    isOverridden: boolean;
    onReset: () => void;
    placeholder?: string;
}) {
    return (
        <div className="space-y-1.5">
            <div className="flex items-center justify-between">
                <div>
                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                        {label}
                    </label>
                    {isOverridden && (
                        <span className="ml-2 text-[10px] font-medium text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 px-1.5 py-0.5 rounded">
                            Override
                        </span>
                    )}
                </div>
                {isOverridden && <ResetButton onClick={onReset} />}
            </div>
            <textarea
                value={value}
                onChange={(e) => onChange(e.target.value)}
                rows={3}
                placeholder={placeholder}
                className="w-full px-4 py-3 rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 text-sm resize-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 transition-all placeholder:text-gray-400"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
        </div>
    );
}

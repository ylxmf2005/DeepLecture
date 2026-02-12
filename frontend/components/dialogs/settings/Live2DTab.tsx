"use client";

import { useEffect, useState } from "react";
import { User, Loader2 } from "lucide-react";
import { CustomSelect } from "@/components/ui/CustomSelect";
import { getLive2DModels, Live2DModel, API_BASE_URL } from "@/lib/api";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";
import { SettingsSection, SettingsCard, SettingsRow } from "./SettingsSection";
import { ToggleSwitch } from "./ToggleSwitch";
import { ScopeAwareField } from "./ScopeAwareField";
import type { SettingsTabProps } from "./types";

const log = logger.scope("Live2DTab");

export function Live2DTab({ scope, settings }: SettingsTabProps) {
    const isVideoScope = scope === "video";
    const { values, isOverridden, clearField } = settings;
    const { live2d } = values;

    const [live2dModels, setLive2dModels] = useState<Live2DModel[]>([]);
    const [modelsLoading, setModelsLoading] = useState(false);

    useEffect(() => {
        if (!live2d.enabled) return;
        const fetchModels = async () => {
            setModelsLoading(true);
            try {
                const models = await getLive2DModels();
                setLive2dModels(models);
            } catch (error) {
                log.error("Failed to fetch Live2D models", toError(error));
            } finally {
                setModelsLoading(false);
            }
        };
        fetchModels();
    }, [live2d.enabled]);

    return (
        <SettingsSection icon={User} title="Live2D Avatar" accentColor="cyan">
            <SettingsCard>
                <ScopeAwareField path="live2d.enabled" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                    <SettingsRow
                        label="Show Avatar"
                        description="Display interactive Live2D avatar on video page"
                    >
                        <ToggleSwitch
                            enabled={live2d.enabled}
                            onChange={settings.toggleLive2d}
                            accentColor="cyan"
                        />
                    </SettingsRow>
                </ScopeAwareField>

                {live2d.enabled && (
                    <>
                        <ScopeAwareField path="live2d.modelPath" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                            <div className="space-y-2 pt-2 border-t border-gray-100 dark:border-gray-700">
                                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                                    Model
                                </label>
                                {modelsLoading ? (
                                    <div className="flex items-center gap-2 py-2">
                                        <Loader2 className="w-4 h-4 animate-spin text-cyan-500" />
                                        <span className="text-sm text-gray-500">Loading models...</span>
                                    </div>
                                ) : (
                                    <CustomSelect
                                        value={live2d.modelPath}
                                        onChange={settings.setLive2dModelPath}
                                        options={
                                            live2dModels.length === 0
                                                ? [{ value: "", label: "No models found" }]
                                                : live2dModels.map((model) => ({
                                                      value: `${API_BASE_URL}${model.path}`,
                                                      label: model.name,
                                                  }))
                                        }
                                        disabled={modelsLoading || live2dModels.length === 0}
                                        accent="cyan"
                                    />
                                )}
                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                    Drag to move, resize from corner. Click avatar to interact.
                                </p>
                            </div>
                        </ScopeAwareField>

                        <ScopeAwareField path="live2d.syncWithVideoAudio" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                            <SettingsRow
                                label="Sync with Video Audio"
                                description="Avatar lip sync follows video audio"
                                withBorder
                            >
                                <ToggleSwitch
                                    enabled={live2d.syncWithVideoAudio}
                                    onChange={settings.toggleLive2dSyncWithVideo}
                                    accentColor="cyan"
                                />
                            </SettingsRow>
                        </ScopeAwareField>
                    </>
                )}
            </SettingsCard>
        </SettingsSection>
    );
}

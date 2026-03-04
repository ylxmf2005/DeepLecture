"use client";

import { useCallback, useEffect, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { FileText, Loader2 } from "lucide-react";
import { toast } from "sonner";
import {
    deletePromptTemplate,
    getAppConfig,
    listPromptTemplates,
} from "@/lib/api";
import type {
    PlaceholderMetadata,
    PromptFunctionConfig,
    PromptTemplate,
} from "@/lib/api";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";
import { isAPIError } from "@/lib/api/errors";
import { SettingsSection, SettingsCard } from "./SettingsSection";
import type { SettingsTabProps } from "./types";
import { TemplateGroupList } from "./prompt/TemplateGroupList";
import { TemplateDrawer } from "./prompt/TemplateDrawer";
import { INITIAL_DRAWER_STATE } from "./prompt/constants";
import type { DrawerState } from "./prompt/constants";

const log = logger.scope("PromptTab");

function mergeTemplatesForDisplay(
    customTemplates: PromptTemplate[],
    promptConfigs: Record<string, PromptFunctionConfig>,
): PromptTemplate[] {
    const customByKey = new Map<string, PromptTemplate>(
        customTemplates.map((template): [string, PromptTemplate] => [
            `${template.funcId}:${template.implId}`,
            template,
        ]),
    );
    const merged: PromptTemplate[] = [];

    for (const [funcId, config] of Object.entries(promptConfigs)) {
        for (const option of config.options) {
            const key = `${funcId}:${option.id}`;
            const customTemplate = customByKey.get(key);
            if (customTemplate) {
                merged.push(customTemplate);
                customByKey.delete(key);
                continue;
            }

            // Built-ins are returned by /config but not by /prompt-templates.
            merged.push({
                funcId,
                implId: option.id,
                name: option.name,
                description: option.description,
                systemTemplate: "",
                userTemplate: "",
                source: "builtin",
                createdAt: null,
                updatedAt: null,
                active: true,
            });
        }
    }

    // Keep unknown leftovers visible instead of silently dropping them.
    for (const template of customByKey.values()) {
        merged.push(template);
    }

    return merged;
}

export function PromptTab({ scope, settings }: SettingsTabProps) {
    const isVideoScope = scope === "video";
    const { values } = settings;
    const { ai } = values;

    const [loading, setLoading] = useState(true);
    const [templates, setTemplates] = useState<PromptTemplate[]>([]);
    const [metadata, setMetadata] = useState<Record<string, PlaceholderMetadata>>({});
    const [promptConfigs, setPromptConfigs] = useState<Record<string, PromptFunctionConfig>>({});
    const [drawer, setDrawer] = useState<DrawerState>(INITIAL_DRAWER_STATE);

    // Fetch both template list (for management) and app config (for active selections)
    const fetchData = useCallback(async (withLoading = false) => {
        if (withLoading) setLoading(true);
        try {
            const [templatesRes, configRes] = await Promise.all([
                listPromptTemplates(),
                getAppConfig(),
            ]);
            setTemplates(mergeTemplatesForDisplay(templatesRes.templates, configRes.prompts));
            setMetadata(templatesRes.metadata);
            setPromptConfigs(configRes.prompts);
        } catch (error) {
            log.error("Failed to fetch prompt data", toError(error));
            toast.error("Failed to load prompt templates");
        } finally {
            if (withLoading) setLoading(false);
        }
    }, []);

    useEffect(() => {
        void fetchData(true);
    }, [fetchData]);

    // Derive active template per funcId from settings + defaults
    const activeTemplates: Record<string, string> = {};
    for (const funcId of Object.keys(promptConfigs)) {
        activeTemplates[funcId] = ai.prompts[funcId] || promptConfigs[funcId]?.defaultImplId || "default";
    }

    const handleSelect = useCallback(
        (funcId: string, implId: string) => {
            const defaultId = promptConfigs[funcId]?.defaultImplId || "default";
            if (implId === defaultId) {
                settings.resetAIPrompt(funcId);
            } else {
                settings.setAIPrompt(funcId, implId);
            }
        },
        [promptConfigs, settings],
    );

    const handleEdit = useCallback((t: PromptTemplate) => {
        // Built-in templates can't be edited in place — open as duplicate instead
        const isBuiltIn = t.source !== "custom";
        setDrawer({
            open: true,
            mode: isBuiltIn ? "duplicate" : "edit",
            funcId: t.funcId,
            sourceTemplate: {
                implId: t.implId,
                name: t.name,
                description: t.description,
                systemTemplate: t.systemTemplate,
                userTemplate: t.userTemplate,
            },
        });
    }, []);

    const handleDuplicate = useCallback((t: PromptTemplate) => {
        setDrawer({
            open: true,
            mode: "duplicate",
            funcId: t.funcId,
            sourceTemplate: {
                implId: t.implId,
                name: t.name,
                description: t.description,
                systemTemplate: t.systemTemplate,
                userTemplate: t.userTemplate,
            },
        });
    }, []);

    const handleCreate = useCallback((funcId: string) => {
        setDrawer({
            open: true,
            mode: "create",
            funcId,
            sourceTemplate: null,
        });
    }, []);

    const handleDelete = useCallback(
        async (t: PromptTemplate) => {
            if (t.source !== "custom") {
                toast.error("Built-in templates cannot be deleted");
                return;
            }
            if (!window.confirm(`Delete template "${t.name}"? This cannot be undone.`)) return;
            try {
                await deletePromptTemplate(t.funcId, t.implId);
                toast.success("Template deleted");
                await fetchData();
            } catch (error) {
                const err = toError(error);
                // 409 Conflict means template is currently selected in global config
                if (isAPIError(error) && error.status === 409) {
                    toast.error("This template is currently selected. Switch to a different template first.");
                } else {
                    toast.error(`Failed to delete: ${err.message}`);
                }
                log.error("Failed to delete template", err);
            }
        },
        [fetchData],
    );

    const handleDrawerClose = useCallback(() => {
        setDrawer(INITIAL_DRAWER_STATE);
    }, []);

    const handleDrawerSaved = useCallback(() => {
        setDrawer(INITIAL_DRAWER_STATE);
        fetchData();
    }, [fetchData]);

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
                {/* Keep drawer height bounded so long template lists don't stretch it */}
                <div className={drawer.open ? "relative h-[70vh] overflow-hidden" : "relative"}>
                    <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed mb-4">
                        Manage AI prompt templates. Click a template to set it as active.
                        {!isVideoScope &&
                            " Use the edit, duplicate, and delete actions to customize."}
                    </p>

                    {!drawer.open && (
                        <TemplateGroupList
                            templates={templates}
                            activeTemplates={activeTemplates}
                            onEdit={handleEdit}
                            onDuplicate={handleDuplicate}
                            onDelete={handleDelete}
                            onSelect={handleSelect}
                            onCreate={handleCreate}
                            isVideoScope={isVideoScope}
                        />
                    )}

                    <AnimatePresence>
                        {drawer.open && (
                            <TemplateDrawer
                                state={drawer}
                                metadata={metadata}
                                onClose={handleDrawerClose}
                                onSaved={handleDrawerSaved}
                            />
                        )}
                    </AnimatePresence>
                </div>
            </SettingsCard>
        </SettingsSection>
    );
}

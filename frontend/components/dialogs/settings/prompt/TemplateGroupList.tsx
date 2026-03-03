"use client";

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { TEMPLATE_CATEGORIES, FUNC_ID_LABELS } from "./constants";
import { TemplateCard } from "./TemplateCard";
import type { PromptTemplate } from "@/lib/api/types";

interface TemplateGroupListProps {
    templates: PromptTemplate[];
    /** Currently active template for each funcId: { funcId → implId } */
    activeTemplates: Record<string, string>;
    onEdit: (template: PromptTemplate) => void;
    onDuplicate: (template: PromptTemplate) => void;
    onDelete: (template: PromptTemplate) => void;
    onSelect: (funcId: string, implId: string) => void;
    onCreate: (funcId: string) => void;
    isVideoScope?: boolean;
}

export function TemplateGroupList({
    templates,
    activeTemplates,
    onEdit,
    onDuplicate,
    onDelete,
    onSelect,
    onCreate,
    isVideoScope,
}: TemplateGroupListProps) {
    const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

    const toggleGroup = useCallback((label: string) => {
        setCollapsed((prev) => ({ ...prev, [label]: !prev[label] }));
    }, []);

    // Index templates by funcId for O(1) lookups
    const templatesByFuncId = templates.reduce<Record<string, PromptTemplate[]>>((acc, t) => {
        (acc[t.funcId] ??= []).push(t);
        return acc;
    }, {});

    return (
        <div className="space-y-3">
            {TEMPLATE_CATEGORIES.map((category) => {
                const Icon = category.icon;
                const isCollapsed = collapsed[category.label] ?? false;
                const categoryTemplates = category.funcIds.flatMap(
                    (fid) => templatesByFuncId[fid] || [],
                );
                const count = categoryTemplates.length;

                return (
                    <div
                        key={category.label}
                        className="rounded-lg border border-gray-100 dark:border-gray-700 overflow-hidden"
                    >
                        {/* Category header */}
                        <button
                            type="button"
                            onClick={() => toggleGroup(category.label)}
                            className="w-full flex items-center gap-2.5 px-3 py-2.5 bg-gray-50/50 dark:bg-gray-800/50 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                            aria-expanded={!isCollapsed}
                        >
                            <Icon className="w-4 h-4 text-orange-500 shrink-0" />
                            <span className="text-xs font-semibold text-gray-700 dark:text-gray-200 flex-1 text-left">
                                {category.label}
                            </span>
                            <span className="text-[10px] text-gray-400 dark:text-gray-500 bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded-full font-medium">
                                {count}
                            </span>
                            <ChevronDown
                                className={cn(
                                    "w-3.5 h-3.5 text-gray-400 transition-transform duration-200",
                                    isCollapsed && "-rotate-90",
                                )}
                            />
                        </button>

                        {/* Collapsible template list */}
                        <AnimatePresence initial={false}>
                            {!isCollapsed && (
                                <motion.div
                                    initial={{ height: 0, opacity: 0 }}
                                    animate={{ height: "auto", opacity: 1 }}
                                    exit={{ height: 0, opacity: 0 }}
                                    transition={{ duration: 0.2, ease: "easeInOut" }}
                                    className="overflow-hidden"
                                >
                                    <div className="px-3 pb-3 pt-1 space-y-3">
                                        {category.funcIds.map((funcId) => {
                                            const funcTemplates = templatesByFuncId[funcId];
                                            if (!funcTemplates || funcTemplates.length === 0)
                                                return null;

                                            const funcLabel =
                                                FUNC_ID_LABELS[funcId]?.label || funcId;
                                            const funcDesc = FUNC_ID_LABELS[funcId]?.desc;
                                            const activeImplId =
                                                activeTemplates[funcId] || "default";

                                            return (
                                                <div key={funcId} className="space-y-1.5">
                                                    <div className="flex items-center justify-between">
                                                        <div>
                                                            <span className="text-[11px] font-medium text-gray-600 dark:text-gray-300">
                                                                {funcLabel}
                                                            </span>
                                                            {funcDesc && (
                                                                <p className="text-[10px] text-gray-400 dark:text-gray-500">
                                                                    {funcDesc}
                                                                </p>
                                                            )}
                                                        </div>
                                                        {!isVideoScope && (
                                                            <button
                                                                type="button"
                                                                onClick={() => onCreate(funcId)}
                                                                className="inline-flex items-center gap-1 text-[10px] font-medium text-orange-600 dark:text-orange-400 hover:text-orange-700 dark:hover:text-orange-300 transition-colors"
                                                                aria-label={`New template for ${funcLabel}`}
                                                            >
                                                                <Plus className="w-3 h-3" />
                                                                New
                                                            </button>
                                                        )}
                                                    </div>
                                                    <div className="space-y-1">
                                                        {funcTemplates.map((t) => (
                                                            <TemplateCard
                                                                key={`${t.funcId}-${t.implId}`}
                                                                name={t.name}
                                                                implId={t.implId}
                                                                description={t.description}
                                                                isDefault={
                                                                    t.source !== "custom"
                                                                }
                                                                isActive={
                                                                    t.implId === activeImplId
                                                                }
                                                                onEdit={() => onEdit(t)}
                                                                onDuplicate={() =>
                                                                    onDuplicate(t)
                                                                }
                                                                onDelete={() => onDelete(t)}
                                                                onSelect={() =>
                                                                    onSelect(funcId, t.implId)
                                                                }
                                                                isVideoScope={isVideoScope}
                                                            />
                                                        ))}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                );
            })}
        </div>
    );
}

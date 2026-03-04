"use client";

import { Copy, Edit2, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface TemplateCardProps {
    name: string;
    implId: string;
    isActive: boolean;
    onEdit: () => void;
    onDuplicate: () => void;
    onDelete: () => void;
    onSelect: () => void;
    /** Hide edit/delete/create actions in video scope */
    isVideoScope?: boolean;
}

export function TemplateCard({
    name,
    implId,
    isActive,
    onEdit,
    onDuplicate,
    onDelete,
    onSelect,
    isVideoScope,
}: TemplateCardProps) {
    return (
        <div
            className={cn(
                "group flex items-center gap-3 rounded-lg border px-3 py-2 transition-colors cursor-pointer",
                isActive
                    ? "border-orange-300 dark:border-orange-700 bg-orange-50/50 dark:bg-orange-900/10"
                    : "border-gray-100 dark:border-gray-700 hover:border-gray-200 dark:hover:border-gray-600 hover:bg-gray-50/50 dark:hover:bg-gray-800/50",
            )}
            onClick={onSelect}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect();
                }
            }}
        >
            {/* Active indicator dot */}
            <div
                className={cn(
                    "w-2 h-2 rounded-full shrink-0",
                    isActive ? "bg-orange-500" : "bg-gray-200 dark:bg-gray-600",
                )}
            />

            {/* Template info */}
            <div className="flex-1 min-w-0">
                <span className="text-xs font-medium text-gray-900 dark:text-gray-100 truncate block">
                    {name}
                </span>
                <span className="text-[10px] font-mono text-gray-400 dark:text-gray-500 truncate block">
                    {implId}
                </span>
            </div>

            {/* Action buttons — hidden in video scope */}
            {!isVideoScope && (
                <div className="flex items-center gap-0.5 shrink-0">
                    <button
                        type="button"
                        onClick={(e) => {
                            e.stopPropagation();
                            onEdit();
                        }}
                        className="p-1 rounded text-gray-400 hover:text-orange-600 dark:hover:text-orange-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                        title="Edit template"
                        aria-label={`Edit ${name}`}
                    >
                        <Edit2 className="w-3 h-3" />
                    </button>
                    <button
                        type="button"
                        onClick={(e) => {
                            e.stopPropagation();
                            onDuplicate();
                        }}
                        className="p-1 rounded text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                        title="Duplicate template"
                        aria-label={`Duplicate ${name}`}
                    >
                        <Copy className="w-3 h-3" />
                    </button>
                    <button
                        type="button"
                        onClick={(e) => {
                            e.stopPropagation();
                            onDelete();
                        }}
                        className="p-1 rounded text-gray-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                        title="Delete template"
                        aria-label={`Delete ${name}`}
                    >
                        <Trash2 className="w-3 h-3" />
                    </button>
                </div>
            )}
        </div>
    );
}

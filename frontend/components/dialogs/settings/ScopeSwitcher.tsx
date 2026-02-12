"use client";

import { Globe, Film } from "lucide-react";
import { cn } from "@/lib/utils";
import type { SettingsScope } from "./useSettingsScope";

interface ScopeSwitcherProps {
    scope: SettingsScope;
    onChange: (scope: SettingsScope) => void;
    hasVideoScope: boolean;
    overrideCount: number;
}

export function ScopeSwitcher({ scope, onChange, hasVideoScope, overrideCount }: ScopeSwitcherProps) {
    if (!hasVideoScope) return null;

    return (
        <div className="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg p-0.5">
            <button
                type="button"
                onClick={() => onChange("global")}
                className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all",
                    scope === "global"
                        ? "bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm"
                        : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300",
                )}
            >
                <Globe className="w-3.5 h-3.5" />
                Global
            </button>
            <button
                type="button"
                onClick={() => onChange("video")}
                className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all",
                    scope === "video"
                        ? "bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm"
                        : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300",
                )}
            >
                <Film className="w-3.5 h-3.5" />
                This Video
                {overrideCount > 0 && (
                    <span className="ml-0.5 min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 text-[10px] font-bold leading-none">
                        {overrideCount}
                    </span>
                )}
            </button>
        </div>
    );
}

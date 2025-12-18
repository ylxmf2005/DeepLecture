"use client";

import { cn } from "@/lib/utils";
import type { ToggleSwitchProps } from "./types";

const ACCENT_COLORS: Record<string, { ring: string; enabled: string }> = {
    rose: { ring: "focus:ring-rose-500/50", enabled: "bg-rose-500 border-rose-500" },
    orange: { ring: "focus:ring-orange-500/50", enabled: "bg-orange-500 border-orange-500" },
    amber: { ring: "focus:ring-amber-500/50", enabled: "bg-amber-500 border-amber-500" },
    cyan: { ring: "focus:ring-cyan-500/50", enabled: "bg-cyan-500 border-cyan-500" },
    violet: { ring: "focus:ring-violet-500/50", enabled: "bg-violet-500 border-violet-500" },
    purple: { ring: "focus:ring-purple-500/50", enabled: "bg-purple-500 border-purple-500" },
    blue: { ring: "focus:ring-blue-500/50", enabled: "bg-blue-500 border-blue-500" },
};

export function ToggleSwitch({
    enabled,
    onChange,
    disabled = false,
    accentColor = "blue",
}: ToggleSwitchProps) {
    const colors = ACCENT_COLORS[accentColor] || ACCENT_COLORS.blue;

    return (
        <button
            type="button"
            onClick={onChange}
            disabled={disabled}
            className={cn(
                "relative inline-flex h-6 w-11 items-center rounded-full border transition-colors focus:outline-none focus:ring-2",
                colors.ring,
                disabled && "opacity-50 cursor-not-allowed",
                enabled
                    ? colors.enabled
                    : "bg-gray-200 dark:bg-gray-700 border-gray-300 dark:border-gray-600"
            )}
        >
            <span
                className={cn(
                    "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform",
                    enabled ? "translate-x-5" : "translate-x-1"
                )}
            />
        </button>
    );
}

"use client";

import { cn } from "@/lib/utils";
import type { SettingsSectionProps } from "./types";

const ACCENT_COLORS: Record<string, string> = {
    blue: "text-blue-600 dark:text-blue-400",
    emerald: "text-emerald-600 dark:text-emerald-400",
    orange: "text-orange-600 dark:text-orange-400",
    violet: "text-violet-600 dark:text-violet-400",
    rose: "text-rose-600 dark:text-rose-400",
    amber: "text-amber-600 dark:text-amber-400",
    purple: "text-purple-600 dark:text-purple-400",
    indigo: "text-indigo-600 dark:text-indigo-400",
    cyan: "text-cyan-600 dark:text-cyan-400",
};

export function SettingsSection({
    icon: Icon,
    title,
    accentColor,
    children,
}: SettingsSectionProps) {
    const colorClass = ACCENT_COLORS[accentColor] || ACCENT_COLORS.blue;

    return (
        <section className="space-y-4">
            <div className={cn("flex items-center gap-2", colorClass)}>
                <Icon className="w-5 h-5" />
                <h3 className="font-semibold text-gray-900 dark:text-gray-100">{title}</h3>
            </div>
            {children}
        </section>
    );
}

export function SettingsCard({ children }: { children: React.ReactNode }) {
    return (
        <div className="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4">
            {children}
        </div>
    );
}

export function SettingsRow({
    label,
    description,
    children,
    withBorder = false,
}: {
    label: string;
    description?: string;
    children: React.ReactNode;
    withBorder?: boolean;
}) {
    return (
        <div
            className={cn(
                "flex items-center justify-between",
                withBorder && "pt-2 border-t border-gray-100 dark:border-gray-700"
            )}
        >
            <div className="flex flex-col">
                <span className="font-medium text-gray-900 dark:text-gray-100">{label}</span>
                {description && (
                    <span className="text-xs text-gray-500 dark:text-gray-400">{description}</span>
                )}
            </div>
            {children}
        </div>
    );
}

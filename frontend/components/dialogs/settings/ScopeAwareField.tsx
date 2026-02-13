"use client";

import { RotateCcw } from "lucide-react";

interface ScopeAwareFieldProps {
    /** Dot-separated path, e.g. "playback.autoPauseOnLeave" */
    path: string;
    isOverridden: (path: string) => boolean;
    onReset: (path: string) => void;
    /** Only show override badge in video scope */
    isVideoScope: boolean;
    children: React.ReactNode;
}

/**
 * Wraps a settings field to show per-video override badge and reset button.
 * In global scope or when not overridden, renders children only.
 */
export function ScopeAwareField({
    path,
    isOverridden,
    onReset,
    isVideoScope,
    children,
}: ScopeAwareFieldProps) {
    const overridden = isVideoScope && isOverridden(path);

    if (!overridden) return <>{children}</>;

    return (
        <div className="flex items-start gap-2">
            <div className="flex-1 min-w-0">{children}</div>
            <div className="flex items-center gap-1 shrink-0 pt-1">
                <span className="text-[10px] font-medium text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 px-1.5 py-0.5 rounded">
                    Override
                </span>
                <button
                    type="button"
                    onClick={() => onReset(path)}
                    className="text-[10px] text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 flex items-center gap-0.5"
                    title="Reset to global default"
                >
                    <RotateCcw className="w-3 h-3" />
                </button>
            </div>
        </div>
    );
}
